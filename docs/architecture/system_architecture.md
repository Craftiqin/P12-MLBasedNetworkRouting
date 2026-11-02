# System architecture

There are two separate simulation paths. The Python path provides fast algorithm experiments on a seeded undirected graph; its Decision Tree is trained on synthetic simulated ACK outcomes. The OMNeT++/INET path is a wireless packet-level six-router AODV baseline. There is no connection from Python model to INET packet forwarding. The four-node ESP32 design is a planned hardware concept only.

Data flow: Python link generator -> feature/ACK dataset -> scikit-learn Decision Tree -> candidate next-hop scorer -> seeded packet simulator -> paired CSV summaries. Separate INET flow: NED topology + INI/XML configuration -> INET AODV UDP experiment -> `.sca`/`.vec`/`.rt` evidence -> exporter summary CSV.
