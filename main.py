# internal imports
from map import get_app


def main():
    # get the map app
    m = get_app()

    # run the app
    # TO RUN IN DOCKER: m.run(host='0.0.0.0')
    # TO RUN   LOCALLY: m.run()
    m.run(host='0.0.0.0')

if __name__ == '__main__':
    main()