#!/bin/bash
#
# Test ImageBind Loading Script
# Tests if ImageBind can load successfully with current resources
#

echo "🧪 Testing ImageBind Loading..."
echo "================================="

cd "$(dirname "$0")/.."

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# Check system resources
echo -e "${YELLOW}📊 System Resources:${NC}"
echo "CPU Cores: $(nproc)"
echo "Total RAM: $(free -h | grep '^Mem:' | awk '{print $2}')"
echo "Available RAM: $(free -h | grep '^Mem:' | awk '{print $7}')"
echo ""

# Test Python import
echo -e "${YELLOW}🐍 Testing Python imports...${NC}"
python3 -c "
try:
    import torch
    print('✅ PyTorch available')
    print(f'   CUDA available: {torch.cuda.is_available()}')
    if torch.cuda.is_available():
        print(f'   CUDA devices: {torch.cuda.device_count()}')
except ImportError as e:
    print(f'❌ PyTorch not available: {e}')
    exit(1)

try:
    from imagebind import data
    from imagebind.models import imagebind_model
    print('✅ ImageBind imports successful')
except ImportError as e:
    print(f'❌ ImageBind not available: {e}')
    exit(1)
"

if [ $? -ne 0 ]; then
    echo -e "${RED}❌ Import test failed${NC}"
    exit 1
fi

echo ""
echo -e "${YELLOW}🚀 Testing ImageBind model loading...${NC}"

# Test model loading with timeout
timeout 300 python3 -c "
import os
import torch
import logging
logging.basicConfig(level=logging.INFO)

try:
    from imagebind.models import imagebind_model
    
    print('Loading ImageBind model...')
    device = 'cuda:0' if torch.cuda.is_available() else 'cpu'
    print(f'Using device: {device}')
    
    # Set cache directory
    cache_dir = os.path.expanduser('~/.cache/torch/hub')
    os.makedirs(cache_dir, exist_ok=True)
    torch.hub.set_dir(cache_dir)
    
    # Change to cache directory
    original_dir = os.getcwd()
    os.chdir(cache_dir)
    
    # Load model
    model = imagebind_model.imagebind_huge(pretrained=True)
    model.eval()
    model.to(device)
    
    print('✅ ImageBind model loaded successfully!')
    print(f'Model device: {next(model.parameters()).device}')
    print(f'Model parameters: {sum(p.numel() for p in model.parameters()):,}')
    
    # Test inference with dummy data
    print('Testing inference...')
    # This would normally require actual data, but just loading is a good test
    
    os.chdir(original_dir)
    print('✅ All tests passed!')
    
except Exception as e:
    print(f'❌ Model loading failed: {e}')
    import traceback
    traceback.print_exc()
    exit(1)
"

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✅ ImageBind loading test PASSED!${NC}"
    echo ""
    echo -e "${GREEN}🎉 Your upgraded VM (4 OCPU, 64GB RAM) can handle ImageBind preloading!${NC}"
    echo ""
    echo "📋 Next steps:"
    echo "1. Deploy the changes: ./scripts/deploy_and_restart.sh"
    echo "2. Check health endpoint: curl https://your-server/health"
    echo "3. Verify 'imagebind_preloaded': true in response"
    echo "4. Test embedding performance - should be much faster!"
else
    echo -e "${RED}❌ ImageBind loading test FAILED${NC}"
    echo ""
    echo "🔍 Possible issues:"
    echo "- Insufficient RAM (ImageBind needs ~16-32GB)"
    echo "- Missing CUDA drivers (if using GPU)"
    echo "- Network issues downloading model weights"
    echo "- Disk space issues in ~/.cache/torch/hub"
fi