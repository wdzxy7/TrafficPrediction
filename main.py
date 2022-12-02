import h5py
import numpy as np

if __name__ == '__main__':
    temp = []
    with h5py.File('TaxiCQ_grid.h5', "r") as f:
        for key in f.keys():
            arr = np.array(f[key])
            print(f[key].shape)
            temp.append(arr)
    data = {}
    '''
    for i, j in zip(temp[0], temp[1]):
        print(i, j)
    '''