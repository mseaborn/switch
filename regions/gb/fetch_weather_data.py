
import calendar
import os
import re
import time
import urllib
import urllib2


def write_file_atomic(filename, data):
    tmp_file = '%s.tmp' % filename
    with open(tmp_file, 'w') as fh:
        fh.write(data)
    os.rename(tmp_file, filename)


def fetch_timepoint(date_arg, time_arg):
    query_data = urllib.urlencode([
        ('Type', 'Observation'),
        ('PredictionSiteID', 'ALL'),
        ('ObservationSiteID', 'ALL'),
        ('Date', date_arg),
        ('PredictionTime', time_arg),
    ])

    request_url = 'https://weather.data.gov.uk/query'
    response = urllib2.urlopen(request_url, query_data)
    response_url = response.geturl()
    assert response_url == request_url, response_url
    code = response.getcode()
    assert code == 200, code
    data = response.read()
    m = re.search('<a href="(https://datagovuk.blob.core.windows.net/csv/[0-9a-f]*.csv)">', data)
    assert m, repr(data)
    next_url = m.group(1)

    response2 = urllib2.urlopen(next_url)
    code = response2.getcode()
    assert code == 200, code
    return response2.read()


def main():
    dest_dir = 'weather_data'
    if not os.path.exists(dest_dir):
        os.mkdir(dest_dir)
    year = 2015
    num_fetches = 0
    start_time = time.time()
    for month in xrange(1, 12 + 1):
        numdays = calendar.monthrange(year, month)[1]
        for day in xrange(1, numdays + 1):
            for hour in xrange(24):
                date_req = '%02d/%02d/%04d' % (day, month, year)
                date_filename = '%04d-%02d-%02d' % (year, month, day)
                time_req = '%02d00' % hour
                filename = os.path.join(
                    dest_dir, '%s-%s.csv' % (date_filename, time_req))
                print filename
                if not os.path.exists(filename):
                    data = fetch_timepoint(date_req, time_req)
                    write_file_atomic(filename, data)
                    num_fetches += 1
                    print '%f s per fetch' % (
                        (time.time() - start_time) / num_fetches)


if __name__ == '__main__':
    main()
