# System architecture

There are two separate simulation paths. The Python path provides fast algorithm experiments on a seeded undirected graph; its Decision Tree is trained on synthetic simulated ACK outcomes. The OMNeT++/INET path preserves a six-router AODV baseline and adds a separate application-level ML forwarder with a C++ Decision Tree. The Python link classifier is not the INET model; both train from synthetic data. The four-node ESP32 design is a planned hardware concept only.

Data flow: Python link generator -> feature/ACK dataset -> scikit-learn Decision Tree -> candidate next-hop scorer -> seeded packet simulator -> paired CSV summaries. Separate INET flows: AODV NED/INI -> AODV UDP runs; ML NED/INI + `MeshRoutingApp` + generated C++ tree -> ML UDP runs. Curated five-seed summaries are checked in; machine-specific raw run folders are excluded.
