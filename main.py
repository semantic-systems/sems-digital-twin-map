# internal imports
from database import connect_db
from map import get_app
from build import build

# external imports
from sqlalchemy import inspect


def main():
    # connect to the database
    engine, session = connect_db()

    # check if the 'features' table exists
    # if not, rebuild the database
    if not inspect(engine).has_table('features'):
        build(verbose=True)
    
    # close the db connection
    session.close()
    engine.dispose()

    # get the map app
    m = get_app()

    # run the app
    # currently configured for a docker container (host='0.0.0.0')
    m.run(host='0.0.0.0')

if __name__ == '__main__':
    main()