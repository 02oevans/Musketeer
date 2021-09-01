import tkinter as tk

import numpy as np

from . import moduleFrame


class GetKsCustom(moduleFrame.Strategy):
    def __init__(self, titration):
        self.titration = titration

    def __call__(self, kVars):
        kVars = np.insert(kVars, 0, 1)
        return self.titration.ksMatrix @ kVars

    def showPopup(self):
        popup = tk.Toplevel()
        popup.title("Edit equilibrium constant values")
        popup.grab_set()
        # TODO: implement


class GetKsAll(moduleFrame.Strategy):
    # when every equilibrium constant is unknown and independent
    def __init__(self, titration):
        self.titration = titration
        titration.ksMatrix = np.identity(titration.boundCount)

    def __call__(self, kVars):
        return kVars


class ModuleFrame(moduleFrame.ModuleFrame):
    frameLabel = "Equilibrium constants"
    dropdownLabelText = "Which Ks to optimise?"
    dropdownOptions = {
        "Optimise all Ks": GetKsAll,
        "Custom": GetKsCustom
    }
    attributeName = "getKs"
