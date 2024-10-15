from os import getenv
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.orm.session import Session
from sqlalchemy.engine.base import Engine

def autoconnect_db(echo=False) -> tuple[Engine, Session]:
    """
    Connect to the database. The hostname is dynamically set depending based on whether the environment variable IN_DOCKER is set to true or false.
    - if IN_DOCKER = true, then hostname = postgis
    - if IN_DOCKER = false, then hostname = localhost\\
    Basically just a simple wrapper around connect_db.
    """

    # load environment variables from .env file
    load_dotenv()

    # set to True to print debug messages
    ALWAYS_PRINT = False

    # the Dockerfile sets the environment variable IN_DOCKER to true
    # otherwise it should not exist
    in_docker: bool = getenv("IN_DOCKER", False)

    # Retrieve database connection details from environment variables
    port = getenv('DB_PORT', None)
    user = getenv('DB_USER', None)
    password = getenv('DB_PASSWORD', None)
    db_name = getenv('DB_NAME', None)

    # If any of the environment variables are not set, raise an error
    if port is None or user is None or password is None or db_name is None:
        raise ValueError("One or more of the required environment variables are not set. See .env.example for more information.")

    # Determine the hostname
    host = "postgis" if in_docker else "localhost"
    if ALWAYS_PRINT: 
        print(f"env IN_DOCKER={in_docker}: hostname={host}")

    # connect to the database
    (engine, session) = connect_db(host=host, port=int(port), user=user, password=password, echo=echo, db_name=db_name)
    
    return (engine, session)

def connect_db(host: str, port: int, user: str, password: str, db_name: str, echo=False):
    """
    Connect to the database. This function builds the database connection string and returns an engine and a session.

    returns ```(engine, session)```
    - `engine` [Engine] SQLAlchemy engine
    - `session` [Session] SQLAlchemy session
    """
    db_string = f"postgresql://{user}:{password}@{host}:{port}/{db_name}"
    engine = create_engine(db_string, echo=echo)
    DBSession = sessionmaker(bind=engine)
    session = DBSession()
    return (engine, session)