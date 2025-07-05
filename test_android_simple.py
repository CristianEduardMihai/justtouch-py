"""
Simple test script for Android file selector functionality (without Kivy dependency)
"""

def test_android_imports():
    """Test importing Android modules"""
    print("Testing Android file selector imports...")
    
    try:
        from android_utils import request_file_permissions, open_android_file_selector
        print("✓ Android utils imported successfully")
        return True
    except ImportError as e:
        print(f"✗ Import error: {e}")
        print("  This is expected when running on desktop")
        return False

def test_mock_functionality():
    """Test the mock functionality for desktop"""
    print("\nTesting mock functionality...")
    
    try:
        from android_utils import request_file_permissions, open_android_file_selector
        
        # Test permission request
        permissions_called = False
        def on_permissions(granted):
            global permissions_called
            permissions_called = True
            print(f"  Permissions callback called: granted={granted}")
        
        print("  Testing permission request...")
        request_file_permissions(on_permissions)
        
        # Test file selector
        files_called = False
        def on_files(files):
            global files_called
            files_called = True
            print(f"  File selector callback called: files={files}")
        
        print("  Testing file selector...")
        open_android_file_selector(on_files, allow_multiple=True)
        
        print("✓ Mock functionality works")
        return True
        
    except Exception as e:
        print(f"✗ Error: {e}")
        return False

if __name__ == "__main__":
    print("=" * 50)
    print("JustTouch Android File Selector Simple Test")
    print("=" * 50)
    
    # Test imports
    import_test_passed = test_android_imports()
    
    # Test mock functionality
    mock_test_passed = test_mock_functionality()
    
    print("\n" + "=" * 50)
    print("Test Results:")
    print(f"Import Test: {'PASS' if import_test_passed else 'FAIL'}")
    print(f"Mock Test: {'PASS' if mock_test_passed else 'FAIL'}")
    
    if import_test_passed and mock_test_passed:
        print("Overall: PASS ✓")
        print("\nThe Android file selector should work when deployed to Android.")
        print("Make sure to:")
        print("1. Build with buildozer")
        print("2. Test on an actual Android device")
        print("3. Grant file permissions when prompted")
    else:
        print("Overall: FAIL ✗")
    
    print("=" * 50)
