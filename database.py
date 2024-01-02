from sqlalchemy import create_engine, Column, Integer, String, ForeignKey, Float, JSON, Table, Boolean
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker
from geoalchemy2 import Geometry

from os import getenv


Base = declarative_base()

class Feature(Base):
    __tablename__ = 'features'
    id = Column(Integer, primary_key=True)
    properties = Column(JSON)
    geometry_type = Column(String, nullable=False)
    geometry = Column(Geometry(geometry_type='GEOMETRY'), nullable=False)
    feature_set_id = Column(Integer, ForeignKey('feature_sets.id'), nullable=False)
    feature_set = relationship('FeatureSet', back_populates='features')    

class FeatureSet(Base):
    __tablename__ = 'feature_sets'
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    features = relationship('Feature', back_populates='feature_set')

    layer_id = Column(Integer, ForeignKey('layers.id'), nullable=False)
    layer = relationship('Layer', back_populates='feature_sets')

    style_id = Column(Integer, ForeignKey('styles.id'), nullable=False)
    style = relationship('Style', back_populates='feature_sets')

    features = relationship('Feature', back_populates='feature_set')

    collection_id = Column(Integer, ForeignKey('collections.id'), nullable=True)    # nullable, because the feature set might not be associated with a collection
    collection = relationship('Collection', back_populates='feature_sets')

class Layer(Base):
    __tablename__ = 'layers'
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    feature_sets = relationship('FeatureSet', back_populates='layer')

class Dataset(Base):
    __tablename__ = 'datasets'
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    description = Column(String)
    url = Column(String, nullable=False)
    collection_identifiers = Column(ARRAY(String), nullable=False)
    collections = relationship('Collection', back_populates='dataset')

class Collection(Base):
    __tablename__ = 'collections'
    id = Column(Integer, primary_key=True)
    identifier = Column(String, nullable=False)
    name = Column(String, nullable=False)
    url_items = Column(String, nullable=False)
    url_collection = Column(String, nullable=False)
    entries = Column(Integer, nullable=False)       # number of items in the collection

    dataset_id = Column(Integer, ForeignKey('datasets.id'), nullable=False)
    dataset = relationship('Dataset', back_populates='collections')

    feature_sets = relationship('FeatureSet', back_populates='collection')

class Colormap(Base):
    __tablename__ = 'colormaps'
    id = Column(Integer, primary_key=True)
    property = Column(String, nullable=False)
    min_value = Column(Float, nullable=False)
    max_value = Column(Float, nullable=False)
    min_color = Column(String, nullable=False)
    max_color = Column(String, nullable=False)
    styles = relationship('Style', back_populates='colormap')

class Style(Base):
    __tablename__ = 'styles'
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    popup_properties = Column(JSON)
    border_color = Column(String)
    area_color = Column(String)
    marker_icon = Column(String)
    marker_color = Column(String)
    line_weight = Column(Float)
    stroke = Column(Boolean) 
    opacity = Column(Float)
    line_cap = Column(String)
    line_join = Column(String)
    dash_array = Column(String)
    dash_offset = Column(String)    # incompatible with old browsers
    fill = Column(Boolean) 
    fill_opacity = Column(Float)
    fill_rule = Column(String)
    colormap_id = Column(Integer, ForeignKey('colormaps.id'), nullable=True)
    colormap = relationship('Colormap', back_populates='styles')
    feature_sets = relationship('FeatureSet', back_populates='style')


def autoconnect_db(port=5432, user="postgres", password="rescuemate", echo=False):
    """
    Connect to the database. The hostname is dynamically set depending based on whether the environment variable IN_DOCKER is set to true or false.
    - if IN_DOCKER = true, then hostname = postgis
    - if IN_DOCKER = false, then hostname = localhost\\
    Basically just a simple wrapper around connect_db.
    """

    ALWAYS_PRINT = True

    (engine, session) = (None, None)   

    in_docker: bool = getenv("IN_DOCKER", False)

    # determine the hostname
    if in_docker:
        if ALWAYS_PRINT: print("\nenv IN_DOCKER=True: hostname=postgis")
        host="postgis"
    else:
        if ALWAYS_PRINT: print("\nenv IN_DOCKER=False: hostname=localhost")	
        host="localhost"

    # connect to the database
    (engine, session) = connect_db(host=host, port=port, user=user, password=password, echo=echo)
    
    return (engine, session)

# create a connection to the database
def connect_db(host="postgis", port=5432, user="postgres", password="rescuemate", echo=False):
    # build the connection string
    db_string = f"postgresql://{user}:{password}@{host}:{port}/postgres"
    engine = create_engine(db_string, echo=echo)
    DBSession = sessionmaker(bind=engine)
    session = DBSession()
    return (engine, session)