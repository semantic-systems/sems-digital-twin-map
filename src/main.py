# Launches the map app
from map.app import get_app
from data.build import build

import sys

def main():
    """
    Launches the map app. Launch parameters:
    -rebuild: rebuilds the database
    -verbose: prints status information when rebuilding the database
    -help: prints this help message
    """

    # launch parameter handling
    params = sys.argv[1:]

    if len(params) > 0:
        # if launched with parameter -rebuild, rebuild the database
        if '-rebuild' in params:

            # if launched with parameter -verbose, print more information
            verbose = '-verbose' in params

            # rebuild the database
            build(verbose=verbose)
        
        # if launched with parameter -help, print the help message
        elif '-help' in params:
            print("""Launch Parameters:
                    -rebuild: rebuilds the database
                    -verbose: prints status information when rebuilding the database
                    -help: prints this help message
                    """)
            return

    # get the map app
    m = get_app()

    # run the app
    m.run(host='0.0.0.0')

if __name__ == '__main__':
    main()