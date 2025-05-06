# Launches the map app
from app.app import get_app
from data.build import build, build_if_uninitialized
import sys
import os

def main():
    """
    Launches the map app. Launch parameters:
    `-rebuild`: rebuilds the database
    `-verbose`: prints status information when used with `-rebuild`
    `-help`: prints this help message
    """

    # launch parameter handling
    params = sys.argv[1:]
    debug = False

    if len(params) > 0:
        
        # if launched with parameter --help, print the help message
        if '--help' in params:
            print("""Launch Parameters:
                    -rebuild: rebuilds the database
                    -verbose: prints status information when rebuilding the database. Must be used with -rebuild
                    -help: prints this help message
                    """)
            return
        
        # if launched with parameter --rebuild, rebuild the database
        if '--rebuild' in params or '-r' in params:

            # if launched with parameter --verbose, print more information
            verbose = '--verbose' in params or '-v' in params

            # rebuild the database
            build(verbose=verbose)
        
        # if launched with parameter --debug, run the app in debug mode
        debug = '--debug' in params or '-d' in params
        if debug: print("Running in debug mode")

    # inspect to see if the database has been built
    # if not, build it
    build_if_uninitialized()

    # get the map app
    m = get_app()

    m.title = "Hamburg Data Map"
    # run the app
    m.run(host='0.0.0.0', debug=debug)

if __name__ == '__main__':
    main()
    