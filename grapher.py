import networkx as nx
import matplotlib.pyplot as plt
from graphviz import Digraph


class Grapher:

    def __init__(self, process_tree):
        self.pt = process_tree

    def drawGraph(self):
        A = nx.nx_agraph.to_agraph(self.pt.process_branches[28].graph)
        A.draw("/home/alxhoff/Downloads/test.png", format='png', prog='dot')



