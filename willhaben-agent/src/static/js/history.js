document.addEventListener('DOMContentLoaded', function () {
    setInterval(updateHistoryTable, 5000); // Update every 5 seconds

    function updateHistoryTable() {
        fetch(`/history_data?page=${page}`)
            .then(response => response.json())
            .then(data => {
                const tbody = document.querySelector('#history-table tbody');
                tbody.innerHTML = '';
                data.data.forEach(item => {
                    const tr = document.createElement('tr');
                    tr.classList.add('border-b');
                    tr.innerHTML = `
                     <td class="py-3 px-6">
                            <a href="${item.url}" target="_blank" rel="noopener noreferrer" class="text-blue-500 break-all hover:underline">
                                ${item.url}
                            </a>
                        </td>
                        <td class="py-3 px-6">
                                <a href=" ${item.source_url}" target="_blank" rel="noopener noreferrer" class="text-blue-500 break-all hover:underline">
                         ${item.source_url}
                             </a>
                         </td>
                        <td class="py-3 px-6">${item.crawled_at}</td>
                    `;
                    tbody.appendChild(tr);
                });
            });
    }
});
