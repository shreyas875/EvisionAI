from sqlalchemy import Column, Integer, String, Float, ForeignKey
from sqlalchemy.orm import relationship
from ..db import Base


class Station(Base):
    __tablename__ = "stations"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    charger_types = Column(String, nullable=False)  # comma-separated e.g. "CCS2,Type2"
    num_ports = Column(Integer, nullable=False, default=4)

    usage = relationship("StationUsage", back_populates="station", cascade="all, delete-orphan")


class StationUsage(Base):
    __tablename__ = "station_usage"

    id = Column(Integer, primary_key=True)
    station_id = Column(Integer, ForeignKey("stations.id"), index=True)
    hour_of_day = Column(Integer, nullable=False)  # 0-23
    avg_cars_per_hour = Column(Float, nullable=False, default=0)

    station = relationship("Station", back_populates="usage")
