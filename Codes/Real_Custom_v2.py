"""Closed Form solution for Custom -di*dj*Fr(i)*Fr(j)/m"""

import itertools
from collections import defaultdict, deque

import networkx as nx
import copy, random
from networkx.utils import py_random_state
import math

import FlowRank as FR
DEBUG = False
#DEBUG = True

def log(s):
    if DEBUG:
        print(s)

@py_random_state("seed")
def louvain_partitions(
    G, weight="weight", resolution=1, threshold=0.0000001, seed=None
):

    partition = [{u} for u in G.nodes()]
    if nx.is_empty(G):
        yield partition
        return
    # mod = modularity(G, partition, resolution=resolution, weight=weight)
    is_directed = G.is_directed()
    if G.is_multigraph():
        graph = _convert_multigraph(G, weight, is_directed)
    else:
        graph = G.__class__()
        graph.add_nodes_from(G)
        graph.add_weighted_edges_from(G.edges(data=weight, default=1))

    #Calculte Flow Rank
    node2FR = dict()
    for i in FR.FLOW_ng(G.edges(),G.nodes(),1):
        node_num = int(i[1])
        node2FR[node_num] = i[0]
    
    m = graph.size(weight="weight")
    partition, inner_partition, improvement, total_improvement = _one_level(
        graph, m, partition, resolution, is_directed, seed, node2FR
    )
    # improvement = True
    total_improvement=threshold+1
    while total_improvement > threshold:
        # gh-5901 protect the sets in the yielded list from further manipulation here
        yield [s.copy() for s in partition]
        # new_mod = modularity(
        #     graph, inner_partition, resolution=resolution, weight="weight"
        # )
        # if new_mod - mod <= threshold:
        #     return
        # mod = new_mod
        graph, node2FR = _gen_graph(graph, inner_partition,node2FR)
        partition, inner_partition, improvement, total_improvement = _one_level(
            graph, m, partition, resolution, is_directed, seed, node2FR
        )

def _one_level(G, m, partition, resolution=1, is_directed=False, seed=None, node2FR={}):

    #nx.draw(G, with_labels=True)
    node2com = {u: i for i, u in enumerate(G.nodes())}
    inner_partition = [{u} for u in G.nodes()]
    if is_directed:
        in_degrees = dict(G.in_degree(weight="weight")) #key = node, value = in_degree
        out_degrees = dict(G.out_degree(weight="weight")) #key = node, value = out_degree
        F_in = {u: in_degrees[u]*node2FR[u] for u in G} #F_in(i) = FR(i)*in_degree(i)
        F_out = {u: out_degrees[u]*node2FR[u] for u in G} #F_out(i) = FR(i)*out_degree(i)
        Stot_in = list(F_in.values()) #Each community's total incoming F(i)
        Stot_out = list(F_out.values()) #Each community's total outgoing F(i)
        # Calculate weights for both in and out neighbors without considering self-loops
        nbrs = {}
        for u in G:
            nbrs[u] = defaultdict(float)
            for _, n, wt in G.out_edges(u, data="weight"):
                if u != n:
                    nbrs[u][n] += wt
            for n, _, wt in G.in_edges(u, data="weight"):
                if u != n:
                    nbrs[u][n] += wt
        # log("nbrs: "+ str(nbrs))
    else:
        nbrs = {u: {v: data["weight"] for v, data in G[u].items() if v != u} for u in G}
    rand_nodes = list(G.nodes)
    seed.shuffle(rand_nodes)
    # log('rand_nodes: '+str(rand_nodes))
    nb_moves = 1
    improvement = False
    total_improvement=0
    while nb_moves > 0:
        nb_moves = 0
        for u in rand_nodes:
            best_mod = 0
            best_com = node2com[u]
            weights2com = _neighbor_weights(nbrs[u], node2com)
            # log('weights2com: '+str(weights2com))
            if is_directed:
                Fin = F_in[u]
                Fout = F_out[u]
                Stot_in[best_com] -= Fin
                Stot_out[best_com] -= Fout
                remove_cost = (
                    -weights2com[best_com] / m
                    + resolution
                    * (Fout * Stot_in[best_com] + Fin * Stot_out[best_com])
                    / m**2
                )
            else:
                # log('skip for now')
                print('')
            for nbr_com, wt in weights2com.items():
                if is_directed:
                    gain = (
                        remove_cost
                        + wt / m
                        - resolution
                        * (
                            Fout * Stot_in[nbr_com]
                            + Fin * Stot_out[nbr_com]
                        )
                        / m**2
                    )
                    # log('u: '+str(u))
                    # log('nbr_com: '+str(nbr_com))
                    # log('inner_partition: '+str(inner_partition))
                    # # log('m: '+str(m))
                    # log('u:'+str(u)+' nbr_com: '+str(inner_partition[nbr_com])+ ' gain: '+str(gain))
                else:
                    # log('skip for now')
                    print('')
                if gain > best_mod:
                    best_mod = gain
                    best_com = nbr_com
                    # log('custom gain: '+str(best_mod))
            if is_directed:
                Stot_in[best_com] += Fin
                Stot_out[best_com] += Fout
            # else:
            #     Stot[best_com] += degree
            if best_com != node2com[u]:
                # print('best_com: ',best_com)
                com = G.nodes[u].get("nodes", {u})
                partition[node2com[u]].difference_update(com)
                inner_partition[node2com[u]].remove(u)
                partition[best_com].update(com)
                inner_partition[best_com].add(u)
                improvement = True
                nb_moves += 1
                node2com[u] = best_com
                total_improvement+=best_mod
            #print("Check",gain,u,inner_partition[nbr_com])
            
    partition = list(filter(len, partition))
    inner_partition = list(filter(len, inner_partition))
    # print('inner_partition: ',inner_partition)
   
    return partition, inner_partition, improvement, total_improvement

def _gen_graph(G, partition, node2FR):
    """Generate a new graph based on the partitions of a given graph"""
    H = G.__class__()
    node2com = {}
    node2FR_new = {}

    for i, part in enumerate(partition):
        nodes = set()
        
        for node in part:
            #New node's FR is the average of all nodes in the community
            node2FR_new[i] = node2FR_new.get(i, 0) + node2FR[node]

            node2com[node] = i
            nodes.update(G.nodes[node].get("nodes", {node}))
       
        #Average the FR of the community
        node2FR_new[i] /= len(part)
        H.add_node(i, nodes=nodes)

    for node1, node2, wt in G.edges(data=True):
        wt = wt["weight"]
        com1 = node2com[node1]
        com2 = node2com[node2]
        temp = H.get_edge_data(com1, com2, {"weight": 0})["weight"]
        H.add_edge(com1, com2, weight=wt + temp)
    return H, node2FR_new

def _neighbor_weights(nbrs, node2com):
    """Calculate weights between node and its neighbor communities.

    Parameters
    ----------
    nbrs : dictionary
           Dictionary with nodes' neighbors as keys and their edge weight as value.
    node2com : dictionary
           Dictionary with all graph's nodes as keys and their community index as value.

    """
    weights = defaultdict(float)
    for nbr, wt in nbrs.items():
        weights[node2com[nbr]] += wt
    return weights

def _convert_multigraph(G, weight, is_directed):
    """Convert a Multigraph to normal Graph"""
    if is_directed:
        H = nx.DiGraph()
    else:
        H = nx.Graph()
    H.add_nodes_from(G)
    for u, v, wt in G.edges(data=weight, default=1):
        if H.has_edge(u, v):
            H[u][v]["weight"] += wt
        else:
            H.add_edge(u, v, weight=wt)
    return H