import networkx as nx
import matplotlib.pyplot as plt
from graphviz import Digraph


class Grapher:

    def __init__(self, process_tree):
        self.pt = process_tree

    def drawGraph(self):
        A = nx.nx_agraph.to_agraph(self.pt.graph)

        all_nodes = A.nodes_iter()

        for node in all_nodes:

            node.attr['style'] = 'filled'
            name = node.get_name()

            if "TaskNode" in name:
                node.attr['fillcolor'] = 'brown1'
            elif "EventSchedSwitch" in name:
                node.attr['fillcolor'] = 'bisque1'
            elif "BinderNode" in name:
                node.attr['fillcolor'] = 'darkolivegreen3'

        A.draw("/home/alxhoff/Downloads/test.xdot", format='xdot', prog='dot')







