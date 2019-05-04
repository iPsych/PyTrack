# -*- coding: utf-8 -*-

import os
import time
import json
import random
import pickle
import tkinter as tk
from datetime import datetime
from functools import partial


import numpy as np
import pandas as pd
import pingouin as pg
import statsmodels.api as sm
import matplotlib.pyplot as plt
from sqlalchemy import create_engine
from matplotlib.widgets import RadioButtons, RectangleSelector
from matplotlib.patches import Rectangle

from Sensor import Sensor
from Subject import Subject


class Visualize:
	
	def __init__(self, master, subjects, exp):
		self.exp = exp
		master.title("PyTrack Visualization")
		self.root = master
		self.v = tk.IntVar()
		self.subjects = subjects

		self.master_frame = tk.Frame(self.root, height=30, width=70)
		self.sub_frame = tk.Frame(self.master_frame, height=30, width=70)
		self.sub_frame.grid_propagate(False)
		self.text = tk.Text(self.sub_frame, width=50)
		
		self.submit_frame = tk.Frame(self.root, width=70)
		func = partial(self.button_click)
		self.submit_btn = tk.Button(self.submit_frame, text="Visualize", command=func)
		self.submit_btn.pack()

		viz_type_frame = tk.Frame(self.root, width=70)
		tk.Radiobutton(viz_type_frame, text="Group Visualization", padx=20, variable=self.v, value=1, command=self.subFrameSetup).pack(side="left", anchor=tk.W)
		tk.Radiobutton(viz_type_frame, text="Individual Visualization", padx=20, variable=self.v, value=2, command=self.subFrameSetup).pack(side="right", anchor=tk.W)
		viz_type_frame.pack(side="top", fill="both", expand=True)
		
		self.master_frame.pack()
		# self.subFrameSetup()

	def subFrameSetup(self):
		
		self.sub_frame.destroy()
		self.submit_frame.pack_forget()

		if self.v.get() == 1:
			
			self.sub_frame = tk.Frame(self.master_frame, height=30, width=70)
			self.sub_frame.grid_propagate(False)
			self.text = tk.Text(self.sub_frame, width=50)

			self.chk_bt_var = [tk.IntVar() for i in range(len(self.subjects))]

			for i, sub in enumerate(self.subjects):
				func = partial(self.button_click, sub)
				chk_bt = tk.Checkbutton(self.sub_frame, text=sub.name, variable=self.chk_bt_var[i], onvalue=1, offvalue=0)
				self.text.window_create(tk.END, window=chk_bt)
				self.text.insert(tk.END, "\n")	
			
			self.submit_frame.pack(side="bottom", fill="both", expand=True)

		else:
			
			self.sub_frame = tk.Frame(self.master_frame, height=30, width=70)
			self.sub_frame.grid_propagate(False)
			self.text = tk.Text(self.sub_frame, width=50)

			for i, sub in enumerate(self.subjects):
				func = partial(self.button_click, sub)
				bt = tk.Button(self.sub_frame, width=30, text=sub.name, command=func)
				self.text.window_create(tk.END, window=bt)
				self.text.insert(tk.END, "\n")	

		vsb = tk.Scrollbar(self.sub_frame, orient="vertical")
		vsb.config(command=self.text.yview)
		
		self.text.configure(yscrollcommand=vsb.set)
		
		self.text.pack(side="left", fill="both", expand=True)
		vsb.pack(side="right", fill="y")

		self.sub_frame.pack(side="bottom", fill="both", expand=True)

	def button_click(self, sub=None):
		if sub == None:
			sub_list = []
			for ind, i in enumerate(self.chk_bt_var):
				if i.get() == 1:
					sub_list.append(self.subjects[ind])
			
			sub_list[0].subjectVisualize(self.root, viz_type="group", sub_list=sub_list)

		else:
			sub.subjectVisualize(self.root)


class Experiment:
	""" This is class responsible for the analysis of data of an entire experiment. The creation of a an object of this class will subsequently create create objects for each 
	`Subject <#module-Subject>`_. involved in the experiment (which in turn would create object for each `Stimulus <#module-Stimulus>`_ which is viewed by the subject). 

	This class also contains the `analyse <#Experiment.Experiment.analyse>`_ function which is used for the statistical analysis of the data (eg: Mixed ANOVA, RM ANOVA etc).

	Parameters
	-----------
	json_file: str
		Name of the json file that contains information regarding the experiment or the database
	reading_method: str {"SQL"| "CSV"}
		Mentions the format in which the data is being stored
	sensors: list(str)
		Contains the names of the different sensors whose indicators are being analysed (currently only Eye Tracking can be done
		However in future versions, analysis of ECG and EDA may be added)
	aoi : str {'NA', 'draw'} | tuple
		If 'NA' then AOI is the entire display size. If 'draw' then the user is prompted to draw an area of interest. If type is ``tuple``, user must specify the coordinates of AOI in the following order (start_x, start_y, end_x, end_y). Here, x is the horizontal axis and y is the vertical axis.

	"""

	def __init__(self, json_file, reading_method="SQL", sensors=["EyeTracker"], aoi="NA"):

		with open(json_file, "r") as json_f:
			json_data = json.load(json_f)

		self.path = json_data["Path"]
		self.name = json_data["Experiment_name"]
		self.json_file = json_file #string
		self.sensors = sensors
		
		self.aoi_coords = None
		# Setting AOI coordinates
		if type(aoi) == str:
			if aoi == "draw":
				self.aoi_coords = self.drawAOI()
			else:
				self.aoi_coords = (0, 0, json_data["Analysis_Params"]["EyeTracker"]["Display_width"], json_data["Analysis_Params"]["EyeTracker"]["Display_height"])
		else:
			self.aoi_coords = aoi
		
		self.columns = self.columnsArrayInitialisation()
		self.stimuli = self.stimuliArrayInitialisation() #dict of names of stimuli demarcated by category
		self.subjects = self.subjectArrayInitialisation(reading_method) #list of subject objects
		self.meta_matrix_dict = (np.ndarray(len(self.subjects), dtype=str), dict())
	
		if not os.path.isdir(self.path + '/Subjects/'):
			os.makedirs(self.path + '/Subjects/')
		

	def stimuliArrayInitialisation(self):
		"""This functions instantiates the dictionary `stimuli` with the list of names of the different stimuli by category

		Parameters
		----------
		json_file : str
			Name of the json file which contains details of the experiment

		Returns
		-------
		data_dict : dict
			Dictionary containing the names of the different stimuli categorised by type

		"""

		with open(self.json_file) as json_f:
			json_data = json.load(json_f)

		stimuli_data = json_data["Stimuli"]

		data_dict = {}

		for k in stimuli_data:
			data_dict[k] = stimuli_data[k]

		return data_dict


	def subjectArrayInitialisation(self, reading_method):
		"""This function initialises an list of objects of class `Subject <#module-Subject>`_.

		Parameters
		----------
		reading_method: str {'SQL','CSV'}, optional
			Specifies the database from which data extraction is to be done from	

		Returns
		-------
		subject_list : list(Subject objects)
			list of objects of class Subject
		
		"""

		with open(self.json_file) as json_f:
			json_data = json.load(json_f)

		subject_list = []	

		subject_data = json_data["Subjects"]

		if reading_method == "SQL":
			name_of_database = json_data["Experiment_name"]
			extended_name = "sqlite:///" + self.path + "/Data/" + name_of_database + ".db"
			database = create_engine(extended_name)
		
		elif reading_method == "CSV":
			database = self.path + "/Data/csv_files"

		for k in subject_data:

			for subject_name in subject_data[k]:

				subject_object = Subject(self.path, subject_name, k, self.stimuli, self.columns, self.json_file, self.sensors, database, reading_method, self.aoi_coords)

				subject_list.append(subject_object)

		if reading_method == "SQL":	
			database.dispose()

		return subject_list


	def columnsArrayInitialisation(self):
		"""The functions extracts the names of the columns that are to be analysed 

		Parameters
		----------
		json_file: str
			Name of the json file which contains details of the experiment

		Returns
		-------
		columns_list: list(str)
			List of names of columns of interest
		
		"""

		with open(self.json_file) as json_f:
			json_data = json.load(json_f)

		column_list = []

		column_classes = [sen for sen in self.sensors]
		column_classes.append("Extra")

		for col_class in column_classes:
			for name in json_data["Columns_of_interest"][col_class]:
				column_list.append(name)

		return column_list


	def visualizeData(self):
		"""Function to open up the GUI for visualizing the data of the experiment.

		This function can be invoked by an `Experiment <#module-Experiment>`_ object. It opens up a window and allows the usee to visualize data such as dynamic gaze and pupil plots, fixation plots and gaze heat maps for individual subjects or aggregate heat maps for a group of subjects on a given stimulus.
		
		"""

		root = tk.Tk()
		root.resizable(False, False)
		viz = Visualize(root, self.subjects, self)
		root.mainloop()

	
	def metaMatrixInitialisation(self, standardise_flag=False, average_flag=False):
		"""This function instantiates the ``meta_matrix_dict`` with values that it extracts from the ``aggregate_meta`` variable of each Subject object.

		Parameters
		----------
		standardise_flag: bool
			Indicates whether the data being considered need to be standardised (by subtracting the control values/baseline value) 
		average_flag: bool
			Indicates whether the data being considered should averaged across all stimuli of the same type 
			NOTE: Averaging will reduce variability and noise in the data, but will also reduce the quantum of data being fed into the statistical test

		"""

		for sensor_type in Sensor.meta_cols:
			for meta_col in Sensor.meta_cols[sensor_type]:
				self.meta_matrix_dict[1].update({meta_col : np.ndarray((len(self.subjects), len(self.stimuli)), dtype=object)})

		#Instantiation of the meta_matrix_dict database		
		for sub_index, sub in enumerate(self.subjects):
			sub.subjectAnalysis(average_flag, standardise_flag)

			self.meta_matrix_dict[0][sub_index] = sub.subj_type

			for stim_index, stimuli_type in enumerate(sub.aggregate_meta):

				for meta in sub.aggregate_meta[stimuli_type]:
					self.meta_matrix_dict[1][meta][sub_index, stim_index] = sub.aggregate_meta[stimuli_type][meta]


	def analyse(self, parameter_list={"all"}, between_factor_list=["Subject_type"], within_factor_list=["Stimuli_type"], statistical_test="Mixed_anova"):
		"""This function carries out the required statistical analysis.
		
		 The analysis is carried out on the specified indicators/parameters using the data extracted from all the subjects that were mentioned in the json file. There are 4 different tests that can be run, namely - Mixed ANOVA, Repeated Measures ANOVA, T Test and Simple ANOVA (both 1 and 2 way)

		Parameters
		----------
		parameter_list: set
			Set of the different indicators/parameters (Pupil_size, Blink_rate) on which statistical analysis is to be performed, by default it will be "all" so that all the parameter are considered. 
		between_factor_list: list(str)
			List of between group factors, by default it will only contain "Subject_type"
			If any additional parameter (eg: Gender) needs to be considered, then the list will be: between_factor_list = ["Subject_type", "Gender"]
			DO NOT FORGET TO INCLUDE "Subject_type", if you wish to consider "Subject_type" as a between group factor.
			Eg: between_factor_list = ["factor_x"] will no longer consider "Subject_type" as a factor. 
			Please go through the README FILE to understand how the JSON FILE is to be written for between group factors to be considered.
		within_factor_list: list(str)
			List of within group factors, by default it will only contain "Stimuli_type"
			If any additional parameter, needs to be considered, then the list will be: between_factor_list = ["Subject_type", "factor_X"]
			DO NOT FORGET TO INCLUDE "Stimuli_type", if you wish to consider "Stimuli_type" as a within group factor.
			Eg: within_factor_list = ["factor_x"] will no longer consider "Stimuli_type" as a factor. 
			Please go through how the README FILE to understand how the JSON FILE is to be written for within group factors to be considered.
		statistical_test: str {"Mixed_anova","RM_anova","ttest","anova"}
			Name of the statistical test that has to be performed.
			NOTE:
			-ttest: Upto 2 between group factors and 2 within group factors can be considered at any point of time
			-Mixed_anova: Only 1 between group factor and 1 within group factor can be considered at any point of time
			-anova: Upto 2 between group factors can be considered at any point of time
			-RM_anova: Upto 2 within group factors can be considered at any point of time  
		
		Examples
		--------
		For calculating Mixed ANOVA, on all the parameters, with standardisation, NOT averaging across stimuli of the same type
		and considering Subject_type and Stimuli_type as between and within group factors respectively

		>>> analyse(self, standardise_flag=False, average_flag=False, parameter_list={"all"}, between_factor_list=["Subject_type"], within_factor_list=["Stimuli_type"], statistical_test="Mixed_anova")
		OR 
		>>> analyse(self, standardise_flag=True) (as many of the option are present by default)

		For calculating 2-way ANOVA, for "blink_rate" and "avg_blink_duration", without standardisation with averaging across stimuli of the same type
		and considering Subject_type and Gender as the between group factors

		>>> analyse(self, average_flag=True, parameter_list={"blink_rate", "avg_blink_duration"}, between_factor_list=["Subject_type", "Gender"], statistical_test="anova")

		"""
		
		#Defining the meta_matrix_dict data structure
		
		with open(self.json_file, "r") as json_f:
			json_data = json.load(json_f)

		meta_not_to_be_considered = ["pupil_size", "pupil_size_downsample"]

		if "GazeAOI" not in json_data["Columns_of_interest"]["EyeTracker"]:
			meta_not_to_be_considered.extend(["no_revisits", "first_pass", "second_pass"])


		for sen in self.sensors: #For each type of sensor

			for meta in Sensor.meta_cols[sen]:
				if meta in meta_not_to_be_considered:
					continue

				if 'all' not in parameter_list:

					if meta not in parameter_list:
						print("The following parameter is not present in the parameter list: ", meta)
						continue

				print("\n\n")
				print("\t\t\t\tAnalysis for ",meta)	

				#For the purpose of statistical analysis, a pandas dataframe needs to be created that can be fed into the statistical functions
				#The columns required are - meta (indicator), the between factors (eg: Subject type or Gender), the within group factor (eg: Stimuli Type), Subject name/id

				#Defining the list of columns required for the statistical analysis
				column_list = [meta]

				column_list.extend(between_factor_list)
				column_list.extend(within_factor_list)
				column_list.append("subject")

				data =  pd.DataFrame(columns=column_list)


				#For each subject
				for sub_index, sub in enumerate(self.subjects):

					#For each Question Type (NTBC: FIND OUT WHAT THE AGGREGATE_META CONTAINS)
					for stimuli_index, stimuli_type in enumerate(sub.aggregate_meta):

						#Value is an array (NTBC : Is it always an array or can it also be a single value?)	
						value_array = self.meta_matrix_dict[1][meta][sub_index,stimuli_index]

						try:					
							for value in value_array:

								row = []

								row.append(value)
								row.append(sub.subj_type)

								#Add the between group factors (need to be defined in the json file)
								for param in between_factor_list:

									if param == "Subject_type":
										continue

									try:
										row.append(json_data["Subjects"][sub.subj_type][sub.name][param])
									except:
										print("Between subject paramter: ", param, " not defined in the json file")	

								row.append(stimuli_type)

								for param in within_factor_list:
									
									if param == "Stimuli_type":
										continue

									try:
										stimulus_name = self.stimuli[stimuli_type][stimuli_index]
										row.append(json_data["Stimuli"][stimuli_type][stimulus_name][param])
									except:
										print("Within stimuli parameter: ", param, " not defined in the json file")

								row.append(sub.name)

								if(np.isnan(value)):
									print("The data being read for analysis contains null value: ", row)

								#Instantiate into the pandas dataframe
								data.loc[len(data)] = row

						except:
							print("Error in data instantiation")

				#Depending on the parameter, choose the statistical test to be done

				if statistical_test == "Mixed_anova":
					print(meta, ":\tMixed anova")
					aov = pg.mixed_anova(dv=meta, within=within_factor_list[0], between=between_factor_list[0], subject = 'subject', data=data)
					pg.print_table(aov)
					posthocs = pg.pairwise_ttests(dv=meta, within=within_factor_list[0], between=between_factor_list[0], subject='subject', data=data)
					pg.print_table(posthocs)

				elif statistical_test == "RM_anova":
					print(meta, ":\tRM Anova")
					aov = pg.rm_anova(dv=meta, within= within_factor_list, subject = 'subject', data=data)
					pg.print_table(aov)


				elif statistical_test == "ttest":
					print(meta, ":\tt test")
					aov = pg.pairwise_ttests(dv=meta, within= within_factor_list, between= between_factor_list, subject='subject', data=data)
					pg.print_table(aov)


				elif statistical_test == "anova":
					print(meta, ":\tANOVA")
					aov = pg.anova(dv = meta, between = between_factor_list, data = data)
					pg.print_table(aov)	


	def getMetaData(self, sub, stim=None, sensor="EyeTracker"):
		"""Function to return the extracted features for a given subject/participant.

		Parameters
		----------
		sub : str
			Name of the subject/participant.
		stim : str | ``None``
			Name of the stimulus. If 'str', the features of the given stimulus will be returned. If ``None``, the features of all stimuli averaged for the different stimuli types (as mentoned in json file) is wanted. 
		sensor : str
			Name of the sensor for which the features is wanted.
		
		Returns
		-------
		dict
			
		Note
		----
		- If the `stim` is ``None``, the returned dictionary is organised as follows 
			{"Stim_TypeA": {"meta1":[], "meta2":[], ...}, "Stim_TypeB": {"meta1":[], "meta2":[], ...}, ...}
		- If the `stim` is ``str``, the returned dictionary is organised as follows 
			{"meta1":[], "meta2":[], ...}
			
		To get the names of all the metadata/features extracted, look at the `Sensor <#module-Sensor>`_ class

		"""
		if stim == None:
			sub_ind = self.subjects.index(sub)
			return self.subjects[sub_ind].aggregate_meta
		
		else:
			sub_ind = self.subjects.index(sub)
			stim_cat = ""
			stim_ind = -1
			for cat in self.stimuli:
				stim_ind = self.stimuli[cat].index(stim)
				if stim_ind != -1:
					stim_cat = cat
					break
			
			return self.subjects[sub_ind].stimulus[stim_cat][stim_ind].sensors[sensor].metadata

	
	def drawAOI(self):
		"""Function that allows speicification of area of interest (AOI) for analysis.

		"""

		with open(self.json_file, "r") as f:
			json_data = json.load(f)
		
		aoi_left_x = 0
		aoi_left_y = 0
		aoi_right_x = 0
		aoi_right_y = 0

		display_width = json_data["Analysis_Params"]["EyeTracker"]["Display_width"]
		display_height = json_data["Analysis_Params"]["EyeTracker"]["Display_height"]

		cnt = 0
		img = None
		
		if os.path.isdir(self.path + "/Stimuli/"):
			for f in os.listdir(self.path + "/Stimuli/"):
				if f.split(".")[-1] in ['jpg', 'jpeg', 'png']:
					img = plt.imread(self.path + "/Stimuli/" + f)
					cnt += 1
					break

		if cnt == 0:
			img = np.zeros((display_height, display_width, 3))

		fig, ax = plt.subplots()
		fig.canvas.set_window_title("Draw AOI")
		ax.imshow(img)

		def line_select_callback(eclick, erelease):
			nonlocal aoi_left_x, aoi_left_y, aoi_right_x, aoi_right_y

			aoi_left_x, aoi_left_y = int(round(eclick.xdata)), int(round(eclick.ydata))
			aoi_right_x, aoi_right_y = int(round(erelease.xdata)), int(round(erelease.ydata))
			
			print("Coordinates [(start_x, start_y), (end_x, end_y)]: ", "[(%6.2f, %6.2f), (%6.2f, %6.2f)]" % (aoi_left_x, aoi_left_y, aoi_right_x, aoi_right_y))
			# rect = Rectangle((min(x1,x2),min(y1,y2)), np.abs(x1-x2), np.abs(y1-y2), color='r', fill=False)
			# ax.add_patch(rect)

		RS = RectangleSelector(ax, line_select_callback, drawtype='box', useblit=False, button=[1],  minspanx=5, minspany=5, spancoords='pixels',interactive=True)

		RS.to_draw.set_visible(True)

		plt.show()
		return (aoi_left_x, aoi_left_y, aoi_right_x, aoi_right_y)