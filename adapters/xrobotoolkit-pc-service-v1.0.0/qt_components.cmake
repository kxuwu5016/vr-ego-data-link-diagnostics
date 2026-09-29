# Upstream CommonUtils/CMakeLists.txt omits the Qt6::Network component import.
# Load the targets before that project's target_link_libraries() call.
find_package(Qt6 REQUIRED COMPONENTS Core Network Core5Compat)
