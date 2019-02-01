from graphviz import Digraph

class grapher:

    def __init__(self):
        self.graph = Digraph(comment='The Round Table')
        self.graph.node('A', 'King Arthur')
        self.graph.node('B', 'Sir Bedevere the Wise')
        self.graph.node('L', 'Sir Lancelot the Brave')
        self.graph.edges(['AB', 'AL'])
        self.graph.edge('B', 'L', constraint='false')
        self.graph.render('test-output/round-table.gv', view=True)

