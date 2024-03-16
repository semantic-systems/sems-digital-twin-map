# Launches the nina server
# This script requests the nina api for alerts every 60 seconds and saves them to the database

from time import sleep
from data.req_nina import save_alerts

VERBOSE = True
REFRESH_RATE = 60   # in seconds

if __name__ == '__main__':

    if VERBOSE:
        print("=========================")
        print('Starting Nina Server.')
        print(f'Refresh rate: {REFRESH_RATE} seconds')
        print('Press Ctrl+C to stop')
        print("=========================")

    while True:

        if VERBOSE:
            print('Requesting... ', end='')

        alerts = save_alerts()
        n_alerts = len(alerts)

        if VERBOSE:
            if n_alerts > 1:
                print(f'Saved {n_alerts} new alerts')
            elif n_alerts == 1:
                print(f'Saved 1 new alert')
            else:
                print('No new alerts')

        sleep(REFRESH_RATE)