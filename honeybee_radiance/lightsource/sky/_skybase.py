from .hemisphere import Hemisphere
from ..ground import Ground
import honeybee.typing as typing
import ladybug.futil as futil


class _Skydome(object):
    """Virtual Skydome base-class with Radiance ground and sky sphere.

    Properties:
        * ground_hemisphere
        * sky_hemisphere
        * is_point_in_time
        * is_climate_based
    """

    __slots__ = ('_ground_hemisphere', '_sky_hemisphere')

    def __init__(self):
        self._ground_hemisphere = Ground()
        self._sky_hemisphere = Hemisphere()

    @property
    def ground_hemisphere(self):
        """Sky ground glow source."""
        return self._ground_hemisphere

    @property
    def sky_hemisphere(self):
        """Sky hemisphere glow source."""
        return self._sky_hemisphere

    @property
    def is_point_in_time(self):
        """Return True if the sky is generated for a single point in time."""
        return False

    @property
    def is_climate_based(self):
        """Return True if the sky is created based on values from weather data."""
        return False

    @classmethod
    def from_dict(cls, input_dict):
        """Create the sky baseclass from a dictionary.

        Args:
            input_dict: A python dictionary in the following format

        .. code-block:: python

            {
                'type': 'SkyDome',
                'ground_hemisphere': {},  # see ground.Ground class [optional],
                'sky_hemisphere': {}  # see hemisphere.Hemisphere class [optional]
            }

        """
        assert 'type' in input_dict, \
            'Input dict is missing type. Not a valid SkyDome dictionary.'
        assert input_dict['type'] == 'SkyDome', \
            'Input type must be SkyDome not %s' % input_dict['type']

        sky = cls()

        if 'ground_hemisphere' in input_dict:
            sky._ground_hemisphere = Ground.from_dict(input_dict['ground_hemisphere'])

        if 'sky_hemisphere' in input_dict:
            sky._sky_hemisphere = Hemisphere.from_dict(input_dict['sky_hemisphere'])

        return sky

    def to_radiance(self):
        """Return radiance definition as a string."""
        return '%s\n\n%s\n' % (self.sky_hemisphere, self.ground_hemisphere)

    def to_dict(self):
        """Translate sky to a dictionary."""
        return {
            'type': 'SkyDome',
            'ground_hemisphere': self.ground_hemisphere.to_dict(),
            'sky_hemisphere': self.sky_hemisphere.to_dict()
        }

    def to_file(self, folder, name=None, mkdir=False):
        """Write sky hemisphere to a sky_hemisphere.rad Radiance file.
        Args:
            folder: Target folder.
            name: File name.
            mkdir: A boolean to note if the directory should be created if doesn't
                exist (default: False).

        Returns:
            Full path to the newly created file.
        """
        content = self.to_radiance()
        name = typing.valid_string(name) if name else 'skydome.rad'
        return futil.write_to_file_by_name(folder, name, content, mkdir)

    def __repr__(self):
        """Sky representation."""
        return self.to_radiance()


class _PointInTime(_Skydome):
    """Point-in-time sky base-class with Radiance ground and sky sphere.

    Properties:
        * ground_hemisphere
        * sky_hemisphere
        * ground_reflectance
        * is_point_in_time
        * is_climate_based
    """

    __slots__ = ('_ground_reflectance',)

    def __init__(self, ground_reflectance):
        _Skydome.__init__(self)
        self.ground_reflectance = ground_reflectance

    @property
    def ground_reflectance(self):
        """Get or set a value between 0 and 1 for the ground reflectance.

        If not specified, a default of 0.2 will be used."""
        return self._ground_reflectance

    @ground_reflectance.setter
    def ground_reflectance(self, ground_reflectance):
        self._ground_reflectance = \
            typing.float_in_range(ground_reflectance, 0, 1, 'ground reflectance') \
            if ground_reflectance is not None else 0.2

    @property
    def is_point_in_time(self):
        """Return True if the sky is generated for a single point in time."""
        return True

    @classmethod
    def from_dict(cls, input_dict):
        """Create the sky baseclass from a dictionary.

        Args:
            input_dict: A python dictionary in the following format

        .. code-block:: python

                {
                'ground_reflectance': 0.2,
                'ground_hemisphere': {},  # see ground.Ground class [optional],
                'sky_hemisphere': {}  # see hemisphere.Hemisphere class [optional]
                }
        """
        sky = cls(input_dict['ground_reflectance'])

        if 'ground_hemisphere' in input_dict:
            sky._ground_hemisphere = Ground.from_dict(input_dict['ground_hemisphere'])

        if 'sky_hemisphere' in input_dict:
            sky._sky_hemisphere = Hemisphere.from_dict(input_dict['sky_hemisphere'])

        return sky

    def to_dict(self):
        """Translate sky to a dictionary."""
        return {
            'ground_reflectance': self.ground_reflectance,
            'ground_hemisphere': self.ground_hemisphere.to_dict(),
            'sky_hemisphere': self.sky_hemisphere.to_dict()
        }
