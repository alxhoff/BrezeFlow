import networkx as nx


class Grapher:

    def __init__(self, process_tree):
        self.pt = process_tree

    def draw_graph(self):
        a_graph = nx.nx_agraph.to_agraph(self.pt.graph)
        a_graph.graph_attr['splines'] = 'polyline'
        a_graph.graph_attr['packmode'] = 'node'
        a_graph.graph_attr['margin'] = 2

        a_graph.draw("/home/alxhoff/Downloads/test.xdot", format='xdot', prog='dot')
