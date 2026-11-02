# Topology

Python topology (`simulator/core.py`): source S, gateway G, relay nodes R1-R4; primary corridors S-R1-R2-G and S-R3-R4-G, with cross-links R1-R3 and R2-R4. Requires at least six nodes. Edges share configured synthetic attributes.

INET topology (`simulation/inet/src/p12ganesh/mesh/IoTMeshNetwork.ned`): gateway node[0], relay-a1 node[1], relay-a2 node[2], relay-b1 node[3], relay-b2 node[4], source node[5]. Fixed positions, `UnitDiskRadioMedium`, AODV routers, IPv4 configurator, UDP application from source to gateway. Effective connectivity follows configured communication range; it is an idealized unit-disk model, not measured RSSI/fading.
