## Instructions for Running the Model
The system is divided into 4 main folders:

Model 2017 (Corresponding to CIC-IDS-2017 data)

Model 2018 (Corresponding to CSE-CIC-IDS-2018 data)

Model UQ (Corresponding to NF-UQ-NIDS data)

Model Cluster

1. How to run the machine learning models
Inside each of the above main folders, there are two subfolders: filter and wrapper.

Each of these subfolders contains 5 pre-configured machine learning models.

How to use: Simply open the model files and select "Run all" to run and get the results.

2. Reference folders (Important note)
Preprocess folder: Contains only the source code for data processing. All three project datasets have been fully pre-processed; therefore, the files in this folder are for reference only and do not need to be run again.

Domain Adaptation Model: This model requires a specific system environment. To run it, you must set up a virtual machine (such as VMWare, WSL, or a native Linux operating system) and have the PyTorch library and CUDA toolset installed. Due to the complexity of the environment, this section is also noted as being for reference only.

Python version requirements Python 3.10.12+