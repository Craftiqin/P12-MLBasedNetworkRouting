package p12ganesh.mesh;

import inet.common.scenario.ScenarioManager;
import inet.networklayer.configurator.ipv4.Ipv4NetworkConfigurator;
import inet.networklayer.ipv4.RoutingTableRecorder;
import inet.node.aodv.AodvRouter;
import inet.physicallayer.wireless.common.medium.UnitDiskRadioMedium;
import inet.visualizer.contract.IIntegratedVisualizer;

network IoTMeshNetwork
{
    parameters:
        int numNodes = default(6);
        @display("bgb=720,520");
    submodules:
        visualizer: <default("IntegratedCanvasVisualizer")> like IIntegratedVisualizer {
            @display("p=660,60");
        }
        configurator: Ipv4NetworkConfigurator {
            @display("p=660,130");
        }
        radioMedium: UnitDiskRadioMedium {
            @display("p=660,200");
        }
        routingTableRecorder: RoutingTableRecorder {
            @display("p=660,270");
        }
        scenarioManager: ScenarioManager {
            @display("p=660,340");
        }
        node[numNodes]: AodvRouter {
            @display("i=device/cellphone;r=,,#707070");
        }
    connections allowunconnected:
}
