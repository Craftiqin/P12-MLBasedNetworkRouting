#ifndef P12GANESH_MESH_ROUTING_APP_H
#define P12GANESH_MESH_ROUTING_APP_H
#include <set>
#include <string>
#include <vector>
#include <map>
#include <omnetpp/clistener.h>
#include "inet/applications/udpapp/UdpBasicApp.h"
#include "inet/common/lifecycle/NodeStatus.h"
#include "../../../ml/generated/runtime-v2/DecisionTreeModel.h"
namespace p12ganesh::mesh {
class MeshRoutingApp : public inet::UdpBasicApp, public omnetpp::cListener {
  protected:
    std::set<int> seen;
    std::set<int> sourcePacketIds;
    std::set<int> deliveredPacketIds;
    std::map<int, std::string> sentRouteById;
    long delivered = 0, forwarded = 0, droppedDuplicate = 0, droppedHopLimit = 0, droppedLoop = 0;
    long selectedUpper = 0, selectedLower = 0, routeChanges = 0;
    int lastRoute = -1;
    double delaySum = 0, hopSum = 0;
    long mlDecisions = 0, mlFallbacks = 0;
    int lastPrediction = -1, lastSelectedRoute = -1;
    bool lastFallback = false;
    p12ganesh::ml::RouteFeatures lastFeatures{};
    int lastUpperAvailable = -1;
    int lastLowerAvailable = -1;
    bool upperReady = true;
    bool lowerReady = true;
    bool upperRecovering = false;
    bool lowerRecovering = false;
    inet::simtime_t lastUpperProbeSent = SIMTIME_ZERO;
    inet::simtime_t lastLowerProbeSent = SIMTIME_ZERO;
    int probeSequence = 0;
    void initialize(int stage) override;
    void receiveSignal(inet::cComponent *source, inet::simsignal_t signalID,
                       inet::cObject *obj, inet::cObject *details) override;
    int chooseRoute();
    void sendRecoveryProbes();
    void sendControlPacket(const std::string& name, int nextHop);
    void writeEvent(const std::string& event, int packetId, const std::string& route,
                    int nextHop, int hops, double delayMs, const std::string& detail);
    void sendPacket() override;
    void processPacket(inet::Packet *packet) override;
    inet::L3Address nodeAddress(int index);
    void finish() override;
};
}
#endif
