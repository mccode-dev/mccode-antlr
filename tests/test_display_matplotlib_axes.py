"""plot_geometry draws McCode's y axis vertically, as its axis labels say."""
import numpy as np
import pytest

matplotlib = pytest.importorskip('matplotlib')
matplotlib.use('Agg')

from mccode_antlr.display.render.matplotlib import plot_geometry  # noqa: E402


def test_beam_along_z_is_drawn_along_the_axis_labelled_z():
    beam = np.array([[0.0, 0.0, 0.0], [0.0, 0.0, 10.0]])
    up = np.array([[0.0, 0.0, 0.0], [0.0, 1.0, 0.0]])
    fig, ax = plot_geometry({'beam': [beam], 'up': [up]}, show_labels=False)
    assert ax.get_ylabel() == 'z (m)' and ax.get_zlabel() == 'y (m)'
    xs, ys, zs = (np.asarray(v) for v in ax.lines[0].get_data_3d())
    assert np.allclose(ys, [0, 10]) and np.allclose(zs, [0, 0])
    xs, ys, zs = (np.asarray(v) for v in ax.lines[1].get_data_3d())
    assert np.allclose(ys, [0, 0]) and np.allclose(zs, [0, 1])
    matplotlib.pyplot.close(fig)
