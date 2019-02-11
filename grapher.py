import networkx as nx
import matplotlib.pyplot as plt

class grapher:

    def __init__(self, graph):
        self.graph = graph

    def drawGraph(self):
        nx.draw_shell(self.graph)
        plt.savefig("result.png")
