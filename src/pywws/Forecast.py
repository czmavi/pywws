# pywws - Python software for USB Wireless Weather Stations
# http://github.com/jim-easterbrook/pywws
# Copyright (C) 2008-18  pywws contributors

# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.

"""Predict future weather using recent data
::

%s

"""

from __future__ import absolute_import, print_function

__docformat__ = "restructuredtext en"
__usage__ = """
 usage: python -m pywws.Forecast [options] data_dir
 options are:
  -h | --help  display this help
 data_dir is the root directory of the weather data
"""
__doc__ %= __usage__
__usage__ = __doc__.split('\n')[0] + __usage__

from datetime import datetime, timedelta
import getopt
import sys

from pywws import DataStore
from pywws import Localisation
from pywws.TimeZone import Local, utc

def _(msg):
    return msg

_forecast_text = {
    'A' : _("Settled fine"),
    'B' : _("Fine weather"),
    'C' : _("Becoming fine"),
    'D' : _("Fine, becoming less settled"),
    'E' : _("Fine, possible showers"),
    'F' : _("Fairly fine, improving"),
    'G' : _("Fairly fine, possible showers early"),
    'H' : _("Fairly fine, showery later"),
    'I' : _("Showery early, improving"),
    'J' : _("Changeable, mending"),
    'K' : _("Fairly fine, showers likely"),
    'L' : _("Rather unsettled clearing later"),
    'M' : _("Unsettled, probably improving"),
    'N' : _("Showery, bright intervals"),
    'O' : _("Showery, becoming less settled"),
    'P' : _("Changeable, some rain"),
    'Q' : _("Unsettled, short fine intervals"),
    'R' : _("Unsettled, rain later"),
    'S' : _("Unsettled, some rain"),
    'T' : _("Mostly very unsettled"),
    'U' : _("Occasional rain, worsening"),
    'V' : _("Rain at times, very unsettled"),
    'W' : _("Rain at frequent intervals"),
    'X' : _("Rain, very unsettled"),
    'Y' : _("Stormy, may improve"),
    'Z' : _("Stormy, much rain")
    }

del _


def ZambrettiCode(params, hourly_data):
    """Simple implementation of Zambretti forecaster algorithm.
    Inspired by beteljuice.com Java algorithm, as converted to Python by
    honeysucklecottage.me.uk, and further information
    from http://www.meteormetrics.com/zambretti.htm"""
    north = eval(params.get('Zambretti', 'north', 'True'))
    baro_upper = eval(params.get('Zambretti', 'baro upper', '1050.0'))
    baro_lower = eval(params.get('Zambretti', 'baro lower', '950.0'))
    if not hourly_data['rel_pressure']:
        return ''
    if hourly_data['wind_ave'] is None or hourly_data['wind_ave'] < 0.3:
        wind = None
    else:
        wind = hourly_data['wind_dir']
    if hourly_data['pressure_trend'] is None:
        trend = 0.0
    else:
        trend = hourly_data['pressure_trend'] / 3.0
    # normalise pressure
    pressure = 950.0 + (
        (1050.0 - 950.0) * (hourly_data['rel_pressure'] - baro_lower) /
        (baro_upper - baro_lower))
    # adjust pressure for wind direction
    if wind is not None:
        if not isinstance(wind, int):
            wind = int(wind + 0.5) % 16
        if not north:
            # southern hemisphere, so add 180 degrees
            wind = (wind + 8) % 16
        pressure += (  5.2,  4.2,  3.2,  1.05, -1.1, -3.15, -5.2, -8.35,
                     -11.5, -9.4, -7.3, -5.25, -3.2, -1.15,  0.9,  3.05)[wind]
    # compute base forecast from pressure and trend (hPa / hour)
    summer = north == (hourly_data['idx'].month >= 4 and
                       hourly_data['idx'].month <= 9)
    if trend >= 0.1:
        # rising pressure
        if summer:
            pressure += 3.2
        F = 0.1740 * (1031.40 - pressure)
        LUT = ('A', 'B', 'B', 'C', 'F', 'G', 'I', 'J', 'L', 'M', 'M', 'Q', 'T',
               'Y')
    elif trend <= -0.1:
        # falling pressure
        if summer:
            pressure -= 3.2
        F = 0.1553 * (1029.95 - pressure)
        LUT = ('B', 'D', 'H', 'O', 'R', 'U', 'V', 'X', 'X', 'Z')
    else:
        # steady
        F = 0.2314 * (1030.81 - pressure)
        LUT = ('A', 'B', 'B', 'B', 'E', 'K', 'N', 'N', 'P', 'P', 'S', 'W', 'W',
               'X', 'X', 'X', 'Z')
    # clip to range of lookup table
    F = min(max(int(F + 0.5), 0), len(LUT) - 1)
    # convert to letter code
    return LUT[F]


def Zambretti(params, hourly_data):
    code = ZambrettiCode(params, hourly_data)
    return Localisation.translation.ugettext(_forecast_text[code])


def main(argv=None):
    if argv is None:
        argv = sys.argv
    try:
        opts, args = getopt.getopt(argv[1:], "h", ['help'])
    except getopt.error as msg:
        print('Error: %s\n' % msg, file=sys.stderr)
        print(__usage__.strip(), file=sys.stderr)
        return 1
    # process options
    for o, a in opts:
        if o in ('-h', '--help'):
            print(__usage__.strip())
            return 0
    # check arguments
    if len(args) != 1:
        print("Error: 1 argument required", file=sys.stderr)
        print(__usage__.strip(), file=sys.stderr)
        return 2
    data_dir = args[0]
    with DataStore.pywws_context(data_dir) as context:
        params = context.params
        Localisation.SetApplicationLanguage(params)
        hourly_data = context.hourly_data
        idx = hourly_data.before(datetime.max)
        print('Zambretti (current):', Zambretti(params, hourly_data[idx]))
        idx = idx.replace(tzinfo=utc).astimezone(Local)
        if idx.hour < 8 or (idx.hour == 8 and idx.minute < 30):
            idx -= timedelta(hours=24)
        idx = idx.replace(hour=9, minute=0, second=0)
        idx = hourly_data.nearest(idx.astimezone(utc).replace(tzinfo=None))
        lcl = idx.replace(tzinfo=utc).astimezone(Local)
        print('Zambretti (at %s):' % lcl.strftime('%H:%M %Z'), Zambretti(
            params, hourly_data[idx]))
    return 0

if __name__ == "__main__":
    sys.exit(main())
