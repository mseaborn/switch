
import csv
import glob


WIND_CF_TABLE_MS = dict((speed, float(kw) / 2500) for speed, kw in [
    # Pairs of (speed in m/s, power output in kW).
    (3, 0),
    (4, 15),
    (5, 105),
    (6, 255),
    (7, 440),
    (8, 675),
    (9, 985),
    (10, 1330),
    (11, 1690),
    (12, 2020),
    (13, 2315),
    (14, 2500),
    (15, 2500),
    (16, 2500),
    (17, 2500),
    (18, 2500),
    (19, 2500),
    (20, 2500),
    (21, 2500),
    (22, 2500),
    (23, 2500),
    (24, 2500),
    (25, 2500),
])

knots_per_ms = 1.943844

def knots_to_ms(knots):
    return knots / knots_per_ms

def get_wind_capacity_factor(speed_knots):
    speed_ms = knots_to_ms(speed_knots)
    if speed_ms >= 25:
        return 0
    a = WIND_CF_TABLE_MS.get(int(speed_ms), 0)
    b = WIND_CF_TABLE_MS.get(int(speed_ms) + 1, 0)
    return a + (b - a) * (speed_ms - int(speed_ms))

WIND_CF_TABLE_KNOTS = dict((knots, get_wind_capacity_factor(knots))
                           for knots in xrange(int(25 * knots_per_ms) + 2))


def main():
    # This prints two things for each site:
    #
    #  * cf=X%: average (mean) capacity factor for the site.
    #  * data=X%: proportion of timepoints for which we have weather
    #    data for this site.

    # Total number of weather observation timepoints.
    obs_count = 0
    # Number of timepoints for each site.
    count_by_site = {}
    # Sum of capacity factors for each site.  Used for calculating the mean.
    cf_sum_by_site = {}

    for filename in glob.glob('weather_data/2015-*.csv'):
        obs_count += 1
        for row in csv.DictReader(open(filename)):
            site = row['Site Name']
            speed = int(row['Wind Speed'])
            count_by_site.setdefault(site, 0)
            count_by_site[site] += 1
            cf_sum_by_site.setdefault(site, 0)
            cf_sum_by_site[site] += WIND_CF_TABLE_KNOTS.get(speed, 0)

    cfs = [(cf_sum_by_site[site] / count_by_site[site], site)
           for site in cf_sum_by_site.iterkeys()]
    for cf, site in sorted(cfs, reverse=True):
        print 'cf=%.1f%%  data=%5.1f%%  %s' % (
            cf * 100, float(count_by_site[site]) / obs_count * 100, site)


if __name__ == '__main__':
    main()
