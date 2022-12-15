import awkward as ak
import numpy as np
np.seterr(all="ignore")
import vector
vector.register_awkward()
import sys

class Particle():
    def __init__(self, tree=None, particle_name=None, particle=None, kin_dict=None):
        """A class much like the TLorentzVector objects in the vector module but with more customizability for my analysis
        """

        if tree is not None and particle_name is not None:
            self.initialize_from_tree(tree, particle_name)
        elif particle is not None:
            self.initialize_from_particle(particle)
        elif kin_dict is not None:
            self.initialize_from_kinematics(kin_dict)

        self.P4 = self.get_vector()
        self.theta = self.P4.theta
        self.costheta = np.cos(self.theta)

    def initialize_from_kinematics(self, kin_dict):
        self.pt = kin_dict['pt']
        self.eta = kin_dict['eta']
        self.phi = kin_dict['phi']
        self.m = kin_dict['m']
        try: self.btag = kin_dict['btag']
        except: pass

    def initialize_from_tree(self, tree, particle_name):
        try: self.pt = getattr(tree, particle_name + '_ptRegressed')
        except: self.pt = getattr(tree, particle_name + '_pt')
        # if 'b' in particle_name and 'gen' not in particle_name:
        self.eta = getattr(tree, particle_name + '_eta')
        self.phi = getattr(tree, particle_name + '_phi')
        self.m = getattr(tree, particle_name + '_m')
        try: self.btag = getattr(tree, particle_name + '_btag')
        except: pass

    def initialize_from_particle(self, particle):
        self.pt = particle.pt
        self.eta = particle.eta
        self.phi = particle.phi
        self.m = particle.m
        try: self.btag = particle.btag
        except: pass

    def get_vector(self):
        p4 = vector.obj(
            pt  = self.pt,
            eta = self.eta,
            phi = self.phi,
            m   = self.m
        )
        return p4

    def set_btag(self, score):
        self.btag = score

    def __add__(self, another_particle):
        particle1 = self.P4
        particle2 = another_particle.P4
        parent = particle1 + particle2
        return Particle(particle=parent)
    
    def boost(self, another_particle):
        return self.P4.boost(-another_particle.P4)

    def deltaEta(self, another_particle):
        return self.P4.deltaeta(another_particle.P4)

    def deltaPhi(self, another_particle):
        return self.P4.deltaphi(another_particle.P4)

    def deltaR(self, another_particle):
        return self.P4.deltaR(another_particle.P4)