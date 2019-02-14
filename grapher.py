import networkx as nx
import ctypes
import matplotlib.pyplot as plt
from graphviz import Digraph


class Grapher:

    def __init__(self, process_tree):
        self.pt = process_tree

    def drawGraph(self):
        A = nx.nx_agraph.to_agraph(self.pt.graph)
        A.graph_attr['splines']='line'
        A.graph_attr['margin']=2
        all_nodes = A.nodes_iter()

        for node in all_nodes:

            # event = node.get_handle()
            # # event = ctypes.POINTER()
            # print event
            # print event.time

            node.attr['style'] = 'filled'
            name = node.get_name()

            if "TaskNode" in name:
                node.attr['fillcolor'] = 'brown1'
            elif "EventSchedSwitch" in name:
                node.attr['fillcolor'] = 'bisque1'
            elif "BinderNode" in name:
                node.attr['fillcolor'] = 'darkolivegreen3'

        A.draw("/home/alxhoff/Downloads/test.xdot", format='xdot', prog='dot')







