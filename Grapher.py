import networkx as nx
import ctypes
import matplotlib.pyplot as plt
from graphviz import Digraph


class Grapher:

    def __init__(self, process_tree):
        self.pt = process_tree

    def drawGraph(self):
        A = nx.nx_agraph.to_agraph(self.pt.graph)
        A.graph_attr['splines']='polyline'
        A.graph_attr['packmode']='node'
        A.graph_attr['margin']=2

        A.draw("/home/alxhoff/Downloads/test.xdot", format='xdot', prog='dot')







