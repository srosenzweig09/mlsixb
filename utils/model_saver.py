from pandas import DataFrame
from pickle import dump
import tensorflow.compat.v1 as tf
tf.disable_v2_behavior()
import tensorflow.python.keras.backend as K
sess = K.get_session()

class ModelSaver():

    def freeze_session(self, session, keep_var_names=None, output_names=None, clear_devices=True):
        """
        Freezes the state of a session into a pruned computation graph.
        Creates a new computation graph where variable nodes are replaced by
        constants taking their current value in the session. The new graph will be
        pruned so subgraphs that are not necessary to compute the requested
        outputs are removed.
        @param session The TensorFlow session to be frozen.
        @param keep_var_names A list of variable names that should not be frozen,
                            or None to freeze all the variables in the graph.
        @param output_names Names of the relevant graph outputs.
        @param clear_devices Remove the device directives from the graph for better portability.
        @return The frozen graph definition.
        """
        graph = session.graph
        with graph.as_default():
            freeze_var_names = list(set(v.op.name for v in tf.global_variables()).difference(keep_var_names or []))
            output_names = output_names or []
            output_names += [v.op.name for v in tf.global_variables()]
            input_graph_def = graph.as_graph_def()
            if clear_devices:
                for node in input_graph_def.node:
                    node.device = ""
            frozen_graph = tf.graph_util.convert_variables_to_constants(
                session, input_graph_def, output_names, freeze_var_names)
            return frozen_graph

    def __init__(self, out_dir, model, history, scaler, is_2b=False):

        # Save to json:  
        hist_json_file = out_dir + f'history.json' 
        json_save = out_dir + f"model.json"
        h5_save   = json_save.replace(".json", ".h5")

        with open(hist_json_file, mode='w') as f:
            history.to_json(f)

        # Save model to json and weights to h5
        model_json = model.to_json()
        with open(json_save, "w") as json_file:
            json_file.write(model_json)

        # serialize weights to HDF5
        model.save_weights(h5_save)

        # save scaler
        dump(scaler, open(out_dir + f'scaler.pkl', 'wb'))

        frozen_graph = self.freeze_session(K.get_session(),
                              output_names=[out.op.name for out in model.outputs])
        tf.train.write_graph(frozen_graph, out_dir, "model.pb", as_text=False)

        print(f"Model saved successfully in {out_dir}")