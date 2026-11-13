"""Adapters: the only code that touches devices, networks or simulators.

Each adapter implements a Protocol from ai_box.core.ports. Adapters may import
ai_box.core.ports; the AI Box may never import an adapter.
"""
