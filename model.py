from sqlalchemy import create_engine, Column, Integer, String, ForeignKey, Float, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from geoalchemy2 import Geometry

Base = declarative_base()

class FeatureSet(Base):
    __tablename__ = 'feature_sets'
    id = Column(Integer, primary_key=True)
    name = Column(String)
    color = Column(String)
    fill_color = Column(String)
    colormap_id = Column(Integer, ForeignKey('colormaps.id'))
    colormap = relationship('Colormap', back_populates='featureSet', uselist=False)
    popup_properties = Column(JSON)
    features = relationship('Feature', back_populates='featureSet')

class Colormap(Base):
    __tablename__ = 'colormaps'
    id = Column(Integer, primary_key=True)
    featureSet = relationship('FeatureSet', back_populates='colormap', uselist=False)
    property = Column(String)
    min_value = Column(Float)
    max_value = Column(Float)
    min_color = Column(String)
    max_color = Column(String)

class Feature(Base):
    __tablename__ = 'features'
    id = Column(Integer, primary_key=True)
    feature_set_id = Column(Integer, ForeignKey('feature_sets.id'))
    properties = Column(JSON)
    type = Column(String)
    featureSet = relationship('FeatureSet', back_populates='features')
    __mapper_args__ = {
        'polymorphic_on': type,
        'polymorphic_identity': 'feature'
    }

class Point(Feature):
    __tablename__ = 'points'
    id = Column(Integer, ForeignKey('features.id'), primary_key=True)
    icon_prefix = Column(String)
    icon_name = Column(String)
    geometry = Column(Geometry(geometry_type='POINT'))
    __mapper_args__ = {
        'polymorphic_identity': 'point'
    }

class Region(Feature):
    __tablename__ = 'regions'
    id = Column(Integer, ForeignKey('features.id'), primary_key=True)
    geometry_type = Column(String)
    geometry = Column(Geometry(geometry_type='GEOMETRY'))
    line_weight = Column(Float)
    __mapper_args__ = {
        'polymorphic_identity': 'region'
    }
