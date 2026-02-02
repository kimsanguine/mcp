// ===== Search Functions =====
function performSearch() {
    const query = document.getElementById('searchInput').value;
    console.log('Searching for:', query);
    // In production, this would call the API
    // For prototype, we just show the existing results
}

function setSearch(term) {
    document.getElementById('searchInput').value = term;
    performSearch();
}

function resetFilters() {
    // Reset all checkboxes
    document.querySelectorAll('.filter-panel input[type="checkbox"]').forEach(cb => {
        cb.checked = false;
    });
    // Reset range slider
    document.getElementById('rateRange').value = 5;
    // Reset select
    document.querySelector('.select-bank').value = '';
}

// ===== Modal Functions =====
function openDetailModal(productId) {
    document.getElementById('detailModal').classList.add('active');
    document.body.style.overflow = 'hidden';
}

function closeDetailModal() {
    document.getElementById('detailModal').classList.remove('active');
    document.body.style.overflow = '';
}

function openProfileModal() {
    document.getElementById('profileModal').classList.add('active');
    document.body.style.overflow = 'hidden';
}

function closeProfileModal() {
    document.getElementById('profileModal').classList.remove('active');
    document.body.style.overflow = '';
}

function saveProfile() {
    // In production, this would save to localStorage or API
    alert('프로필이 저장되었습니다.');
    closeProfileModal();
}

// ===== Event Listeners =====
document.addEventListener('DOMContentLoaded', () => {
    // Close modal when clicking overlay
    document.querySelectorAll('.modal-overlay').forEach(overlay => {
        overlay.addEventListener('click', (e) => {
            if (e.target === overlay) {
                overlay.classList.remove('active');
                document.body.style.overflow = '';
            }
        });
    });

    // Close modal with Escape key
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
            document.querySelectorAll('.modal-overlay.active').forEach(modal => {
                modal.classList.remove('active');
            });
            document.body.style.overflow = '';
        }
    });

    // Search on Enter key
    document.getElementById('searchInput').addEventListener('keypress', (e) => {
        if (e.key === 'Enter') {
            performSearch();
        }
    });

    // Range slider update
    const rateRange = document.getElementById('rateRange');
    if (rateRange) {
        rateRange.addEventListener('input', (e) => {
            document.querySelector('.current-value').textContent = `최대 ${e.target.value}%`;
        });
    }
});

// ===== Admin Dashboard Functions =====
function updateWeight(type, value) {
    console.log(`${type} weight updated to:`, value);
    document.querySelector(`#${type}Value`).textContent = value;
}

function applyWeights() {
    const vectorWeight = document.getElementById('vectorWeight')?.value || 1.0;
    const bm25Weight = document.getElementById('bm25Weight')?.value || 1.0;
    const rrfK = document.getElementById('rrfK')?.value || 60;

    console.log('Applying weights:', { vectorWeight, bm25Weight, rrfK });
    alert(`설정이 적용되었습니다.\nVector: ${vectorWeight}\nBM25: ${bm25Weight}\nRRF K: ${rrfK}`);
}

function testConfiguration() {
    alert('테스트 검색을 실행합니다...');
}
