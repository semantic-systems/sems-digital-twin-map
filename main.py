# internal imports
from database import Base, Feature, FeatureSet, Style, Colormap, connect_db
from map import build_map
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

    # build the map
    m = build_map(session)

    # save the map
    m.save('map.html')

if __name__ == '__main__':
    main()