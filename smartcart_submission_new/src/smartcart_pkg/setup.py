import os
from glob import glob
from setuptools import setup

package_name = 'smartcart_pkg'

# ★重要：この関数定義のインデントに注意
def package_files(directory_list):
    paths = []
    for directory in directory_list:
        for (path, directories, filenames) in os.walk(directory):
            for filename in filenames:
                file_path = os.path.join(path, filename)
                install_path = os.path.join('share', package_name, path)
                paths.append((install_path, [file_path]))
    return paths

# データファイルの定義
data_files = [
    ('share/ament_index/resource_index/packages', ['resource/' + package_name]),
    ('share/' + package_name, ['package.xml']),
    (os.path.join('share', package_name, 'launch'), glob('launch/*.launch.py')),
    (os.path.join('share', package_name, 'maps'), glob('maps/*')),
    (os.path.join('share', package_name, 'worlds'), glob('worlds/*')),
]

# modelsフォルダを追加
data_files.extend(package_files(['models']))

# ★ここが一番重要です！
# 以下の setup(...) は行頭（左端）にあり、インデントされてはいけません
setup(
    name=package_name,
    version='0.0.1',
    packages=[package_name],
    data_files=data_files,
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='User',
    maintainer_email='user@todo.todo',
    description='Smart Cart Project',
    license='TODO: License declaration',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            'simple_navigator = smartcart_pkg.simple_navigator:main',
            'cart_scanner = smartcart_pkg.cart_scanner:main',
            'shopping_navigator = smartcart_pkg.shopping_navigator_real:main',
            # app.pyに main()関数がない場合は以下の行を削除してください
            'app = smartcart_pkg.app:main', 
        ],
    },
)