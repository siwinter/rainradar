import setuptools
 
with open("README.md", "r") as fh:
    long_description = fh.read()
 
setuptools.setup(
    name='rainradar',  
    version='0.0.1',
    author="siwinter",
#    author_email="andrew@ao.gl",
    description="A virtual rainsensor",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/siwinter/rainradar",
    packages=["rainradar"],
    entry_points = {
        "console_scripts": ['rainradar = rainradar.rainradar:main']
    },
    install_requires=[
		'tornado', 
		'paho-mqtt',
		'systemd'
		],
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
)
