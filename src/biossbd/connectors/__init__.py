"""Connectors to external open-source tools and public databases.

- :mod:`.pubchem`   PubChem (NIH): compound search, GHS hazard statements, flash point,
  explosive and exposure limits
- :mod:`.openlca`   openLCA 2 desktop application via IPC
- :mod:`.brightway` Brightway 2.5 projects, databases, activities and methods
- :mod:`.owid`      Our World in Data: country context (electricity carbon intensity)
"""
from .http import ConnectorError, NotFound

__all__ = ["ConnectorError", "NotFound"]
