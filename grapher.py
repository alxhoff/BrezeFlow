import networkx as nx
import matplotlib.pyplot as plt
from graphviz import Digraph


class Grapher:

    def __init__(self, process_tree):
        self.pt = process_tree

    def drawGraph(self):
        A = nx.nx_agraph.to_agraph(self.pt.graph)
        A.draw("/home/alxhoff/Downloads/test.png", format='png', prog='dot')

        # add sub-graph of PID 3035
        # graph_3035 = nx.nx_agraph.to_agraph(self.pt.process_branches[])

        # subgraph_count = len(self.pt.process_branches[28].tasks)
        # for x,task in enumerate(self.pt.process_branches[28].tasks):
        #     task_graph = nx.nx_agraph.to_agraph(task.graph)
        #     task_graph.draw("/home/alxhoff/Downloads/test_task" + str(x) + ".png", format='png',
        #                     prog='dot')





