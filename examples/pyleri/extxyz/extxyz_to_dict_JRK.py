import sys
import json
import re
import numpy as np

from pyleri.node import Node
from pyleri import Choice, Regex, Keyword, Token
from extxyz_kv_NB_grammar import ExtxyzKVGrammar

class NodeVisitor:
    """
    Implementation of the Visitor pattern for a pyleri parse tree.
    Walks the tree calling a visitor function for every node found. The
    visitor methods should be defined in subclasses as ``visit_`` plus the
    class name of the element, e.g. ``visit_Regex`. If no visitor function is
    found the `generic_visit` visitor is used instead.
    """

    def visit(self, node):
        method = 'visit_' + node.element.__class__.__name__
        visitor = getattr(self, method, self.generic_visit)
        return visitor(node)

    def generic_visit(self, node):
        for child in node.children:
            self.visit(child)                
                
class NodeTransformer(NodeVisitor):
    """
    Subclass of `Visitor` which allows tree to be modified.
    Walks the parse tree and uses the return value of the
    visitor methods to replace or remove old nodes. If the return
    value of the visitor method is ``None``, the node will be removed.
    """

    def generic_visit(self, node):
        new_children = []
        for child in node.children:
            child = self.visit(child)
            if child is None:
                continue
            elif isinstance(child, list):
                new_children.extend(child)
                continue
            new_children.append(child)
        node.children[:] = new_children
        return node


class TreeDumper(NodeVisitor):
    """
    Subclass of `NodeVisitor` which prints a textual representation
    of the parse tree.
    """

    def __init__(self):
        self.depth = 0
        
    def generic_visit(self, node):
        name = node.element.name if hasattr(node.element, 'name') else None
        print('  ' * self.depth + f'{node.element.__class__.__name__}(name={name}, string="{node.string}")')
        self.depth += 1
        super().generic_visit(node)
        self.depth -= 1

        
class TreeCleaner(NodeTransformer):
    def visit_Token(self, node):
        return None
    
    def visit_Choice(self, node):
        name = getattr(node, 'name', None)
        # if name == 'key_item', 'val_item']:
        #     return self.generic_visit(node)
        return [self.generic_visit(child) for child in node.children]
    
    # def visit_Regex(self, node):
    #     if getattr(node, 'name', None) is None:
    #         return None        
    #     return self.generic_visit(node)
        
if __name__ == '__main__':
    grammar = ExtxyzKVGrammar()

    test_line = sys.stdin.readline().strip()
    result = grammar.parse(test_line)

    top = result.tree.children[0]
    clean = TreeCleaner().visit(top)
    TreeDumper().visit(clean)