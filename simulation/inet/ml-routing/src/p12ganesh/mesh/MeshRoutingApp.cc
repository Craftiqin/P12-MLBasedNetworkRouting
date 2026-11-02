#include "MeshRoutingApp.h"
#include <fstream>
#include <iomanip>
#include <sstream>
#include <string>
#include "inet/applications/base/ApplicationPacket_m.h"
#include "inet/common/TimeTag_m.h"
#include "inet/common/socket/SocketTag_m.h"
#include "inet/common/Simsignals.h"
#include "inet/common/lifecycle/NodeStatus.h"
#include "inet/networklayer/common/L3AddressTag_m.h"
#include "inet/transportlayer/common/L4PortTag_m.h"
#include "../../../ml/generated/runtime-v2/DecisionTreeModel.h"
using namespace inet;
using namespace p12ganesh::mesh;
Define_Module(MeshRoutingApp);

static const std::vector<int> upperPath{5,2,1,0};
static const std::vector<int> lowerPath{5,4,3,0};


static L3Address addressForNode(int index) {
    return L3Address(Ipv4Address(10, 0, 0, index + 1));
}

void MeshRoutingApp::initialize(int stage) {
    UdpBasicApp::initialize(stage);
    if (stage == INITSTAGE_LOCAL) {
        auto status = getParentModule()->getSubmodule("status");
        if (status)
            status->subscribe(NodeStatus::nodeStatusChangedSignal, this);
    }
}

void MeshRoutingApp::receiveSignal(cComponent *source, simsignal_t signalID,
                                   cObject *obj, cObject *details) {
    if (signalID == NodeStatus::nodeStatusChangedSignal) {
        auto status = check_and_cast<NodeStatus *>(obj);
        const char *state = status->getState() == NodeStatus::UP ? "UP" :
                            status->getState() == NodeStatus::DOWN ? "DOWN" :
                            status->getState() == NodeStatus::GOING_UP ? "GOING_UP" : "GOING_DOWN";
        EV_INFO << "NODE_STATUS node=" << getParentModule()->getIndex()
                << " state=" << state << " (module state only; path readiness requires packet proof)" << endl;
    }
}

int MeshRoutingApp::chooseRoute() {
    if (par("strategy").stdstringValue() != "ml") {
        lastPrediction = lastSelectedRoute = 0;
        lastFallback = false;
        return 0;
    }
    auto operational = [this](int index) {
        auto node = getParentModule()->getParentModule()->getSubmodule("node", index);
        auto status = node ? node->getSubmodule("status") : nullptr;
        auto nodeStatus = dynamic_cast<NodeStatus *>(status);
        return nodeStatus == nullptr || nodeStatus->getState() == NodeStatus::UP;
    };
    bool upperUp = operational(2) && operational(1);
    bool lowerUp = operational(4) && operational(3);
    auto updatePathStatus = [this](const char *path, bool nodeStatusUp, int &lastStatus,
                                   bool &ready, bool &recovering) {
        if (lastStatus == 1 && !nodeStatusUp) {
            ready = false;
            recovering = true;
            EV_INFO << "FAILURE_DETECTED time=" << simTime() << " path=" << path
                    << " evidence=NodeStatus_DOWN" << endl;
            writeEvent("failure_detected", -1, path, -1, 0, -1.0, "NodeStatus_DOWN");
        }
        else if (lastStatus == 0 && nodeStatusUp) {
            ready = false;
            recovering = true;
            EV_INFO << "PATH_STATUS_UP time=" << simTime() << " path=" << path
                    << " evidence=NodeStatus_UP; active_probe_required" << endl;
            writeEvent("path_status_up", -1, path, -1, 0, -1.0, "awaiting_end_to_end_probe");
        }
        if (!nodeStatusUp) {
            ready = false;
            recovering = true;
        }
        lastStatus = nodeStatusUp ? 1 : 0;
    };
    updatePathStatus("upper", upperUp, lastUpperAvailable, upperReady, upperRecovering);
    updatePathStatus("lower", lowerUp, lastLowerAvailable, lowerReady, lowerRecovering);
    lastFeatures = {
        upperUp && upperReady ? 1.0 : 0.0,
        par("upperPdrEstimate").doubleValue(), par("upperLatencyEstimateMs").doubleValue(), 3.0,
        lowerUp && lowerReady ? 1.0 : 0.0,
        par("lowerPdrEstimate").doubleValue(), par("lowerLatencyEstimateMs").doubleValue(), 3.0
    };
    lastPrediction = p12ganesh::ml::predict(lastFeatures);
    lastSelectedRoute = p12ganesh::ml::selectSafely(lastPrediction, lastFeatures);
    lastFallback = lastSelectedRoute != lastPrediction;
    return lastSelectedRoute;
}

void MeshRoutingApp::sendControlPacket(const std::string& name, int nextHop) {
    auto packet = new Packet(name.c_str());
    auto payload = makeShared<ApplicationPacket>();
    payload->setChunkLength(B(1));
    payload->setSequenceNumber(probeSequence);
    payload->addTag<CreationTimeTag>()->setCreationTime(simTime());
    packet->insertAtBack(payload);
    packet->addTag<L3AddressReq>()->setDestAddress(addressForNode(nextHop));
    socket.sendTo(packet, addressForNode(nextHop), destPort);
}

void MeshRoutingApp::sendRecoveryProbes() {
    if (getParentModule()->getIndex() != 5)
        return;
    auto operational = [this](int index) {
        auto node = getParentModule()->getParentModule()->getSubmodule("node", index);
        auto status = node ? node->getSubmodule("status") : nullptr;
        auto nodeStatus = dynamic_cast<NodeStatus *>(status);
        return nodeStatus == nullptr || nodeStatus->getState() == NodeStatus::UP;
    };
    auto probe = [this](const char *route, const std::vector<int>& path, bool recovering,
                        bool ready, simtime_t& lastSent) {
        if (!recovering || ready || simTime() - lastSent < 1.0)
            return;
        int id = probeSequence++;
        std::ostringstream name;
        name << "MeshProbe|" << id << "|" << route << "|1|0";
        sendControlPacket(name.str(), path[1]);
        lastSent = simTime();
        EV_INFO << "ROUTE_PROBE_SENT time=" << simTime() << " probe=" << id
                << " route=" << route << " nextHop=" << path[1] << endl;
        writeEvent("path_probe_sent", id, route, path[1], 0, -1.0, "active_end_to_end_probe");
    };
    probe("upper", upperPath, upperRecovering && operational(2) && operational(1), upperReady, lastUpperProbeSent);
    probe("lower", lowerPath, lowerRecovering && operational(4) && operational(3), lowerReady, lastLowerProbeSent);
}

void MeshRoutingApp::writeEvent(const std::string& event, int packetId, const std::string& route,
                                int nextHop, int hops, double delayMs, const std::string& detail) {
    const std::string path = par("eventLog").stdstringValue();
    if (path.empty()) return;
    std::ifstream existing(path);
    bool writeHeader = !existing || existing.peek() == std::ifstream::traits_type::eof();
    existing.close();
    std::ofstream out(path, std::ios::app);
    if (!out) throw cRuntimeError("Cannot open MeshRoutingApp event log: %s", path.c_str());
    if (writeHeader)
        out << "time_s,event,packet_id,node_id,route,predicted_route,selected_route,next_hop_id,fallback,"
               "upper_available,upper_pdr_estimate,upper_latency_ms,lower_available,lower_pdr_estimate,"
               "lower_latency_ms,hops,delay_ms,model_version,detail\n";
    auto routeText = [](int value) { return value == 0 ? "upper" : value == 1 ? "lower" : "none"; };
    out << std::setprecision(12) << simTime().dbl() << ',' << event << ',' << packetId << ','
        << getParentModule()->getIndex() << ',' << route << ',' << routeText(lastPrediction) << ','
        << routeText(lastSelectedRoute) << ',' << nextHop << ',' << (lastFallback ? 1 : 0) << ','
        << lastFeatures.upper_available << ',' << lastFeatures.upper_pdr_estimate << ','
        << lastFeatures.upper_latency_ms << ',' << lastFeatures.lower_available << ','
        << lastFeatures.lower_pdr_estimate << ',' << lastFeatures.lower_latency_ms << ','
        << hops << ',' << delayMs << ',' << p12ganesh::ml::MODEL_VERSION << ',' << detail << '\n';
}

void MeshRoutingApp::sendPacket() {
    if (getParentModule()->getIndex() != 5) return;
    int selected = chooseRoute();
    sendRecoveryProbes();
    const int packetId = numSent;
    sourcePacketIds.insert(packetId);
    if (par("strategy").stdstringValue() == "ml") {
        writeEvent("decision", packetId, selected == 0 ? "upper" : selected == 1 ? "lower" : "none",
                   selected == 0 ? 2 : selected == 1 ? 4 : -1, 0, -1.0, "");
        ++mlDecisions;
        if (lastFallback) ++mlFallbacks;
        EV_INFO << "PACKET event=generated time=" << simTime() << " packet=" << packetId
                << " prediction=" << lastPrediction << " selected=" << selected
                << " nextHop=" << (selected == 0 ? 2 : selected == 1 ? 4 : -1)
                << " fallback=" << lastFallback << endl;
    }
    bool routeChanged = lastRoute != selected;
    if (lastRoute >= 0 && routeChanged) ++routeChanges;
    if (par("strategy").stdstringValue() == "ml" && routeChanged)
        EV_INFO << "ML_ROUTE t=" << simTime() << " packet=" << packetId
                << " model=" << p12ganesh::ml::MODEL_VERSION
                << " prediction=" << lastPrediction << " selected=" << selected
                << " nextHop=" << (selected == 0 ? 2 : selected == 1 ? 4 : -1)
                << " fallback=" << lastFallback
                << " upperAvailable=" << lastFeatures.upper_available
                << " upperPdrEstimate=" << lastFeatures.upper_pdr_estimate
                << " upperLatencyEstimateMs=" << lastFeatures.upper_latency_ms
                << " lowerAvailable=" << lastFeatures.lower_available
                << " lowerPdrEstimate=" << lastFeatures.lower_pdr_estimate
                << " lowerLatencyEstimateMs=" << lastFeatures.lower_latency_ms << endl;
    if (par("strategy").stdstringValue() == "ml" && routeChanged)
        EV_INFO << "ROUTE_CHANGED time=" << simTime() << " packet=" << packetId
                << " route=" << (selected == 0 ? "upper" : selected == 1 ? "lower" : "none")
                << " nextHop=" << (selected == 0 ? 2 : selected == 1 ? 4 : -1) << endl;
    lastRoute = selected;
    if (selected < 0) {
        sentRouteById[packetId] = "none";
        EV_INFO << "PACKET event=dropped time=" << simTime() << " packet=" << packetId
                << " node=5 reason=no_available_candidate" << endl;
        writeEvent("packet_generated", packetId, "none", -1, 0, -1.0, "");
        writeEvent("no_route_drop", packetId, "none", -1, 0, -1.0, "no_available_candidate");
        ++numSent;
        return;
    }
    if (selected == 0) ++selectedUpper; else ++selectedLower;
    const auto &path = selected == 0 ? upperPath : lowerPath;
    sentRouteById[packetId] = selected == 0 ? "upper" : "lower";
    std::ostringstream name;
    name << "MeshData|" << packetId << "|" << (path == upperPath ? "upper" : "lower") << "|1|1";
    writeEvent("packet_generated", packetId, selected == 0 ? "upper" : "lower", path[1], 0, -1.0, "");
    auto packet = new Packet(name.str().c_str());
    packet->addTag<CreationTimeTag>()->setCreationTime(simTime());
    auto payload = makeShared<ApplicationPacket>();
    payload->setChunkLength(B(par("messageLength")));
    payload->setSequenceNumber(packetId);
    payload->addTag<CreationTimeTag>()->setCreationTime(simTime());
    packet->insertAtBack(payload);
    emit(packetSentSignal, packet);
    // Clear receive-side metadata before reusing packet for another UDP send.
    packet->removeTagIfPresent<L3AddressReq>();
    packet->removeTagIfPresent<L3AddressInd>();
    packet->removeTagIfPresent<L4PortReq>();
    packet->addTag<L3AddressReq>()->setDestAddress(addressForNode(path[1]));
    socket.sendTo(packet, addressForNode(path[1]), destPort);
    ++numSent;
}

void MeshRoutingApp::processPacket(Packet *packet) {
    emit(packetReceivedSignal, packet);
    std::string name = packet->getName();
    if (name.rfind("MeshProbe|", 0) == 0 || name.rfind("MeshProbeAck|", 0) == 0) {
        bool ack = name.rfind("MeshProbeAck|", 0) == 0;
        std::stringstream control(name);
        std::string token;
        std::vector<std::string> parts;
        while (std::getline(control, token, '|')) parts.push_back(token);
        if (parts.size() != 5 || (parts[2] != "upper" && parts[2] != "lower")) {
            delete packet;
            return;
        }
        int id = std::stoi(parts[1]);
        const std::string& route = parts[2];
        int position = std::stoi(parts[3]);
        int hops = std::stoi(parts[4]);
        const auto& path = route == "upper" ? upperPath : lowerPath;
        int here = getParentModule()->getIndex();
        EV_INFO << "ROUTE_PROBE_HOP_RECEIVED time=" << simTime() << " probe=" << id
                << " kind=" << (ack ? "ack" : "request") << " route=" << route
                << " node=" << here << " position=" << position << endl;
        if (position < 0 || position >= (int)path.size() || path[position] != here) {
            EV_INFO << "ROUTE_PROBE_DROPPED time=" << simTime() << " probe=" << id
                    << " route=" << route << " node=" << here << " reason=path_position_mismatch" << endl;
            delete packet;
            return;
        }
        if (!ack && here == 0) {
            int nextPosition = position - 1;
            std::ostringstream response;
            response << "MeshProbeAck|" << id << "|" << route << "|" << nextPosition << "|" << hops + 1;
            sendControlPacket(response.str(), path[nextPosition]);
            EV_INFO << "ROUTE_PROBE_REPLY time=" << simTime() << " probe=" << id
                    << " route=" << route << " nextHop=" << path[nextPosition] << endl;
            delete packet;
            return;
        }
        if (ack && here == 5) {
            if (route == "upper") { upperReady = true; upperRecovering = false; }
            else { lowerReady = true; lowerRecovering = false; }
            EV_INFO << "ROUTE_PROBE_SUCCESS time=" << simTime() << " probe=" << id
                    << " route=" << route << " hops=" << hops
                    << " evidence=forward_and_return_packet" << endl;
            writeEvent("path_probe_success", id, route, -1, hops, -1.0, "forward_and_return_packet");
            delete packet;
            return;
        }
        int nextPosition = ack ? position - 1 : position + 1;
        if (nextPosition < 0 || nextPosition >= (int)path.size()) {
            delete packet;
            return;
        }
        std::ostringstream nextName;
        nextName << (ack ? "MeshProbeAck|" : "MeshProbe|") << id << "|" << route
                 << "|" << nextPosition << "|" << hops + 1;
        packet->setName(nextName.str().c_str());
        packet->removeTagIfPresent<L3AddressReq>();
        packet->removeTagIfPresent<L3AddressInd>();
        packet->removeTagIfPresent<L4PortReq>();
        packet->removeTagIfPresent<SocketInd>();
        packet->addTag<L3AddressReq>()->setDestAddress(addressForNode(path[nextPosition]));
        socket.sendTo(packet, addressForNode(path[nextPosition]), destPort);
        return;
    }
    std::stringstream ss(name);
    std::string token;
    std::vector<std::string> fields;
    while (std::getline(ss, token, '|')) fields.push_back(token);
    if (fields.size() != 5 || fields[0] != "MeshData") { delete packet; return; }
    int seq = std::stoi(fields[1]);
    const std::string route = fields[2];
    int position = std::stoi(fields[3]);
    int hops = std::stoi(fields[4]);
    if (route != "upper" && route != "lower") {
        ++droppedLoop;
        EV_INFO << "PACKET event=dropped time=" << simTime() << " packet=" << seq
                << " node=" << getParentModule()->getIndex() << " reason=invalid_route_name" << endl;
        writeEvent("loop_drop", seq, route, -1, hops, -1.0, "invalid_route_name");
        delete packet;
        return;
    }
    auto routeNodes = route == "upper" ? upperPath : lowerPath;
    int here = getParentModule()->getIndex();
    writeEvent("packet_received", seq, route, -1, hops, -1.0, "");
    if (position < 0 || position >= (int)routeNodes.size()) {
        EV_INFO << "PACKET event=dropped time=" << simTime() << " packet=" << seq
                << " node=" << here << " reason=route_position_out_of_range" << endl;
        ++droppedLoop; writeEvent("loop_drop", seq, route, -1, hops, -1.0, "route_position_out_of_range"); delete packet; return;
    }
    if (!seen.insert(seq).second) {
        EV_INFO << "PACKET event=dropped time=" << simTime() << " packet=" << seq
                << " node=" << here << " reason=duplicate_packet" << endl;
        ++droppedDuplicate; writeEvent("duplicate_drop", seq, route, -1, hops, -1.0, "packet_id_seen_at_node"); delete packet; return;
    }
    if (routeNodes[position] != here) {
        EV_INFO << "PACKET event=dropped time=" << simTime() << " packet=" << seq
                << " node=" << here << " reason=route_position_mismatch" << endl;
        ++droppedLoop; writeEvent("loop_drop", seq, route, -1, hops, -1.0, "route_position_mismatch"); delete packet; return;
    }
    if (hops > par("maxHops").intValue()) {
        EV_INFO << "PACKET event=dropped time=" << simTime() << " packet=" << seq
                << " node=" << here << " reason=hop_limit_exceeded hops=" << hops << endl;
        ++droppedHopLimit; writeEvent("hop_limit_drop", seq, route, -1, hops, -1.0, "max_hops_exceeded"); delete packet; return;
    }
    ++numReceived;
    EV_INFO << "PACKET event=received time=" << simTime() << " packet=" << seq
            << " node=" << here << " route=" << route << " hops=" << hops << endl;
    if (here == 0) {
        ++delivered;
        deliveredPacketIds.insert(seq);
        auto tag = packet->findTag<CreationTimeTag>();
        double delay = tag ? (simTime() - tag->getCreationTime()).dbl() : -1.0;
        if (delay >= 0) delaySum += delay;
        hopSum += hops;
        writeEvent("packet_delivered", seq, route, -1, hops, delay >= 0 ? delay * 1000.0 : -1.0, "");
        EV_INFO << "PACKET event=delivered time=" << simTime() << " packet=" << seq
                << " node=0 hops=" << hops << " delay_s=" << (delay >= 0 ? delay : -1.0)
                << " route=" << route << endl;
        delete packet;
        return;
    }
    int nextPosition = position + 1;
    if (nextPosition >= (int)routeNodes.size() || routeNodes[nextPosition] == here) {
        EV_INFO << "PACKET event=dropped time=" << simTime() << " packet=" << seq
                << " node=" << here << " reason=invalid_next_hop" << endl;
        ++droppedLoop; writeEvent("loop_drop", seq, route, -1, hops, -1.0, "invalid_next_hop"); delete packet; return;
    }
    ++forwarded;
    EV_INFO << "PACKET event=forwarded time=" << simTime() << " packet=" << seq
            << " node=" << here << " nextHop=" << routeNodes[nextPosition]
            << " route=" << route << " hops=" << hops + 1 << endl;
    writeEvent("packet_forwarded", seq, route, routeNodes[nextPosition], hops + 1, -1.0, "");
    std::ostringstream nextName;
    nextName << "MeshData|" << seq << "|" << route << "|" << nextPosition << "|" << (hops + 1);
    packet->setName(nextName.str().c_str());
    packet->removeTagIfPresent<L3AddressReq>();
    packet->removeTagIfPresent<L3AddressInd>();
    packet->removeTagIfPresent<L4PortReq>();
    packet->addTag<L3AddressReq>()->setDestAddress(addressForNode(routeNodes[nextPosition]));
    // UDP delivery leaves the previous socket id on the payload. Dispatcher
    // would route this recycled packet back to this app instead of UDP.
    packet->removeTagIfPresent<SocketInd>();
    socket.sendTo(packet, addressForNode(routeNodes[nextPosition]), destPort);
}

void MeshRoutingApp::finish() {
    recordScalar("mesh delivered", delivered);
    recordScalar("route upper selections", selectedUpper);
    recordScalar("route lower selections", selectedLower);
    recordScalar("route changes", routeChanges);
    recordScalar("mesh forwarded", forwarded);
    recordScalar("mesh duplicate drops", droppedDuplicate);
    recordScalar("mesh hop-limit drops", droppedHopLimit);
    recordScalar("mesh loop drops", droppedLoop);
    recordScalar("mesh mean delay seconds", delivered ? delaySum / delivered : 0);
    recordScalar("mesh mean hop count", delivered ? hopSum / delivered : 0);
    recordScalar("mesh generated", numSent);
    recordScalar("ML decisions", mlDecisions);
    recordScalar("ML fallbacks", mlFallbacks);
    if (getParentModule()->getIndex() == 5)
        EV_INFO << "ML_SUMMARY generated=" << numSent << " routeChanges=" << routeChanges
                << " decisions=" << mlDecisions << " fallbacks=" << mlFallbacks << endl;
    if (getParentModule()->getIndex() == 5) {
        auto gatewayNode = getParentModule()->getParentModule()->getSubmodule("node", 0);
        auto gatewayApp = gatewayNode ? dynamic_cast<MeshRoutingApp *>(gatewayNode->getSubmodule("app", 0)) : nullptr;
        if (gatewayApp) {
            for (int packetId : sourcePacketIds) {
                if (gatewayApp->deliveredPacketIds.count(packetId) == 0) {
                    const std::string route = sentRouteById.count(packetId) ? sentRouteById.at(packetId) : "unknown";
                    EV_INFO << "PACKET event=dropped time=" << simTime() << " packet=" << packetId
                            << " node=5 route=" << route
                            << " reason=no_gateway_delivery_by_end cause=unresolved_link_or_network_loss" << endl;
                    writeEvent("packet_not_delivered", packetId, route, -1, 0, -1.0,
                               "no_gateway_delivery_by_end_cause_unresolved");
                }
            }
        }
    }
    if (getParentModule()->getIndex() == 0)
        EV_INFO << "ML_DELIVERY_SUMMARY delivered=" << delivered
                << " meanDelaySeconds=" << (delivered ? delaySum / delivered : 0)
                << " meanPacketHops=" << (delivered ? hopSum / delivered : 0)
                << " forwarded=" << forwarded << " duplicateDrops=" << droppedDuplicate
                << " loopDrops=" << droppedLoop << " hopLimitDrops=" << droppedHopLimit << endl;
    UdpBasicApp::finish();
}
