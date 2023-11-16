from sqlalchemy import create_engine, Column, Integer, String, ForeignKey, Float, JSON, Table
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker
from geoalchemy2 import Geometry


Base = declarative_base()

class Feature(Base):
    __tablename__ = 'features'
    id = Column(Integer, primary_key=True)
    properties = Column(JSON)
    geometry_type = Column(String, nullable=False)
    geometry = Column(Geometry(geometry_type='GEOMETRY'), nullable=False)
    feature_set_id = Column(Integer, ForeignKey('feature_sets.id'))
    feature_set = relationship('FeatureSet', back_populates='features')

class FeatureSet(Base):
    __tablename__ = 'feature_sets'
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    style_id = Column(Integer, ForeignKey('styles.id'), nullable=True)
    style = relationship('Style', back_populates='feature_sets')
    features = relationship('Feature', back_populates='feature_set')

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
    color = Column(String)
    fill_color = Column(String)
    icon_prefix = Column(String)
    icon_name = Column(String)
    line_weight = Column(Float)
    colormap_id = Column(Integer, ForeignKey('colormaps.id'), nullable=True)
    colormap = relationship('Colormap', back_populates='styles')
    feature_sets = relationship('FeatureSet', back_populates='style')

# create a connection
def connect_db(host="postgis", port=5432, user="postgres", password="rescuemate", echo=False):
    # build the connection string
    db_string = f"postgresql://{user}:{password}@{host}:{port}/postgres"
    engine = create_engine(db_string, echo=echo)
    DBSession = sessionmaker(bind=engine)
    session = DBSession()
    return (engine, session)