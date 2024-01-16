from os import getenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

def autoconnect_db(port=5432, user="postgres", password="rescuemate", echo=False):
    """
    Connect to the database. The hostname is dynamically set depending based on whether the environment variable IN_DOCKER is set to true or false.
    - if IN_DOCKER = true, then hostname = postgis
    - if IN_DOCKER = false, then hostname = localhost\\
    Basically just a simple wrapper around connect_db.
    """

    # set to True to print debug messages
    ALWAYS_PRINT = False

    # the Dockerfile sets the environment variable IN_DOCKER to true
    # otherwise it should not exist
    in_docker: bool = getenv("IN_DOCKER", False)

    # determine the hostname
    if in_docker:
        if ALWAYS_PRINT: print("env IN_DOCKER=True: hostname=postgis")
        host="postgis"
    else:
        if ALWAYS_PRINT: print("env IN_DOCKER=False: hostname=localhost")	
        host="localhost"

    # connect to the database
    (engine, session) = connect_db(host=host, port=port, user=user, password=password, echo=echo)
    
    return (engine, session)

def connect_db(host="postgis", port=5432, user="postgres", password="rescuemate", echo=False):
    """
    Connect to the database. This function builds the database connection string and returns an engine and a session.

    returns ```(engine, session)```
    - `engine` [Engine] SQLAlchemy engine
    - `session` [Session] SQLAlchemy session
    """
    db_string = f"postgresql://{user}:{password}@{host}:{port}/postgres"
    engine = create_engine(db_string, echo=echo)
    DBSession = sessionmaker(bind=engine)
    session = DBSession()
    return (engine, session)