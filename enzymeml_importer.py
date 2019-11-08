import COPASI
import sys
import os
sys.path.append(os.path.abspath("./python-enzymeml"))
import enzymeml.enzymeml as enzml

dm = COPASI.CRootContainer.addDatamodel()
assert (isinstance(dm, COPASI.CDataModel))


class EnzymeMLImporter:

    def __init__(self, file_name, out_dir='.'):
        self.name = os.path.splitext(os.path.basename(file_name))[0]
        self.file_name = file_name
        self.out_dir = out_dir
        self.copasi_file = os.path.join(out_dir, self.name + ".cps")
        self.data_file = os.path.join(out_dir, self.name + ".txt")
        self.archive = None

    @staticmethod
    def _get_species_by_sbml(id):
        for metab in dm.getModel().getMetabolites():
            if metab.sbml_id == id:
                return metab
        return None

    @staticmethod
    def _get_cn_by_id(id):
        metab = EnzymeMLImporter._get_species_by_sbml(id)
        if metab is None:
            return ''
        return metab.getConcentrationReference().getCN()

    def _write_experimental_data(self):

        reaction_data = self.archive.reaction_data

        # figure out our columns
        all_columns = {}
        max_num_replicas = 1
        all_cols = []
        col_cn_map = {}

        data_dict = {}

        time = set()

        for file_entry in reaction_data.listOfFiles.files.values():
            format = reaction_data.listOfFormats.formats[file_entry.format]
            column_definitions = format.columns
            count = 0
            for col in column_definitions:
                if col.type == 'time' and 'time' not in all_cols:
                    all_columns['time'] = []
                    all_cols.append('time')
                    col_cn_map['time'] = dm.getModel().getValueReference().getCN()
                    for entry in file_entry.columns[count]:
                        time.add(entry)
                    count += 1
                    continue
                if col.type =='conc':
                    if col.species not in all_cols:
                        all_columns[col.species] = []
                        all_cols.append(col.species)
                        col_cn_map[col.species] = self._get_cn_by_id(col.species)
                    if col.replica not in all_columns[col.species]:
                        all_columns[col.species].append(col.replica)
                        max_num_replicas = max(max_num_replicas, len(all_columns[col.species]))
                        data_dict[(col.species, col.replica)] = file_entry.columns[count]
                count += 1

        time = sorted(time)

        # now analyze the reaction, to prepare data for later
        needed_data = {}
        for reaction in self.archive.reaction_condition.items():
            id = reaction[0]
            if id not in needed_data:
                needed_data[id] = []
            for entry in reaction[1].replicas:
                needed_data[id].append((entry.measurement, entry.replica))

        for measurement in reaction_data.listOfMeasurements.measurements.values():
            file_entry = reaction_data.listOfFiles.files[measurement.file]
            data = file_entry.columns
            format = reaction_data.listOfFormats.formats[file_entry.format]
            column_definitions = format.columns

        line_count = 1
        # write experiment file
        with open(self.data_file, 'w') as data:
            # write header
            for i in range(len(all_cols)):
                data.write(all_cols[i])
                if i+1 < len(all_cols):
                    data.write('\t')
            data.write('\n')

            # write data
            for rowcount in range(len(time)):
                for replica_index in range(max_num_replicas):
                    for col in range(len(all_cols)):
                        if col == 0:
                            data.write(str(time[rowcount]))
                        else:
                            species = all_cols[col]
                            replica = all_columns[species][replica_index] if replica_index < len(all_columns[species]) \
                                else None
                            if replica is not None:
                                value = data_dict[(species, replica)][rowcount]
                                if value is not None:
                                    data.write(str(value))

                        if col + 1 < len(all_cols):
                            data.write('\t')
                    line_count += 1
                    data.write('\n')

        # now create mapping for COPASI
        task = dm.getTask('Parameter Estimation')
        task.setScheduled(True)  # mark task as executable, so it can be run by copasi se
        problem = task.getProblem()
        problem.setCalculateStatistics(False)  # disable statistics at the end of the runs
        exp_set = problem.getExperimentSet()

        exp = COPASI.CExperiment(dm)
        exp = exp_set.addExperiment(exp)
        info = COPASI.CExperimentFileInfo(exp_set)
        info.setFileName(str(self.data_file))
        exp.setObjectName(self.name)
        exp.setFirstRow(1)
        exp.setLastRow(line_count)
        exp.setHeaderRow(1)
        exp.setFileName(str(os.path.basename(self.data_file)))
        exp.setExperimentType(COPASI.CTaskEnum.Task_timeCourse)
        exp.setSeparator('\t')
        exp.setNumColumns(len(all_cols))

        # now do the mapping
        obj_map = exp.getObjectMap()
        obj_map.setNumCols(len(all_cols))
        for i in range(len(all_cols)):
            role = COPASI.CExperiment.ignore
            if all_cols[i] == 'time':
                role = COPASI.CExperiment.time
            else:
                if all_cols[i] in col_cn_map:
                    cn = col_cn_map[all_cols[i]]
                    role = COPASI.CExperiment.dependent
                    obj_map.setRole(i, role)
                    obj_map.setObjectCN(i, cn)
                    exp.calculateWeights()
                    continue
            obj_map.setRole(i, role)

    def convert(self):

        self.archive = enzml.EnzymeML(self.name)
        assert (isinstance(self.archive, enzml.EnzymeML))
        self.archive.load_from_file(self.file_name)

        # import sbml model
        sbml = self.archive.master.toSBML()
        if not dm.importSBMLFromString(sbml):
            raise ValueError("Couldn't import SBML model: " + COPASI.CCopasiMessage.getAllMessageText())

        dm.saveModel(self.copasi_file, True)

        # convert data
        self._write_experimental_data()
        dm.saveModel(self.copasi_file, True)

        # add plot for progress & result
        dm.loadModel(self.copasi_file)
        task = dm.getTask('Parameter Estimation')
        task.setMethodType(COPASI.CTaskEnum.Method_Statistics)
        COPASI.COutputAssistant.getListOfDefaultOutputDescriptions(task)
        COPASI.COutputAssistant.createDefaultOutput(913, task, dm)
        COPASI.COutputAssistant.createDefaultOutput(910, task, dm)
        dm.saveModel(self.copasi_file, True)

        pass

    @staticmethod
    def import_enzymeml(file_name, out_dir):
        converter = EnzymeMLImporter(file_name, out_dir)
        converter.convert()


if __name__ == "__main__":
    num_args = len(sys.argv)

    if num_args > 2:
        file_name = sys.argv[1]
        out_dir = sys.argv[2]
    else:
        file_name = './example/model_example.omex'
        out_dir = './out'

    EnzymeMLImporter.import_enzymeml(file_name, out_dir)
