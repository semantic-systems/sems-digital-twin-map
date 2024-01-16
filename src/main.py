# Launches the map app
from map.app import get_app

def main():
    # get the map app
    m = get_app()

    # run the app
    m.run(host='0.0.0.0')

if __name__ == '__main__':
    main()