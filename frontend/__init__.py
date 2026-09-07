"""
frontend
Presentation layer: the landing page, the 3D observation-network globe and
the design system.

Modules inside this package import each other RELATIVELY (``from . import
theme``). Absolute imports would resolve through sys.path, where a
same-named package could shadow this one, and a half-shadowed package is a
very confusing failure to diagnose.
"""
