
import hashlib
import os
import subprocess


def hash_file(filename):
    hasher = hashlib.sha1()
    fh = open(filename, 'rb')
    while True:
        data = fh.read(0x1000)
        if len(data) == 0:
            break
        hasher.update(data)
    return hasher.hexdigest()


def check_hash(filename, expected_hash):
    actual_hash = hash_file(filename)
    if actual_hash != expected_hash:
        raise Exception('File %r has hash %r instead of expected hash %r'
                        ' -- delete the file and try again'
                        % (filename, actual_hash, expected_hash))


def fetch_url(filename, url, expected_hash):
    if os.path.exists(filename):
        # Check the existing file just in case.
        check_hash(filename, expected_hash)
        return

    temp_file = '%s.tmp' % filename
    subprocess.check_call(['wget', '-c', url, '-O', temp_file])
    check_hash(temp_file, expected_hash)
    os.rename(temp_file, filename)


def main():
    fetch_url(
        'demand_2015.csv',
        'http://www2.nationalgrid.com/WorkArea/DownloadAsset.aspx?id=8589934640',
        '1222a31e7455211392500ea210aeb17e754a278c')


if __name__ == '__main__':
    main()
