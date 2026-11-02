package p12ganesh.mesh;
import inet.applications.udpapp.UdpBasicApp;
simple MeshRoutingApp extends UdpBasicApp
{
    parameters:
        @class(p12ganesh::mesh::MeshRoutingApp);
        string strategy = default("baseline");
        int maxHops = default(4);
        double upperPdrEstimate = default(0.985);
        double upperLatencyEstimateMs = default(34);
        double lowerPdrEstimate = default(0.955);
        double lowerLatencyEstimateMs = default(47);
        string eventLog = default("");
}
