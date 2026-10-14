# Coverage và kế hoạch bổ sung Pha 3

Counts dưới đây được tính từ frozen gold, **không phải điểm chạy hệ thống**.

Legacy: 50 case; 46 family; nhãn {'publish': 41, 'abstain': 4, 'conditional': 5}.
Multi-turn legacy: 0; support có operation overlay cụ thể: 2.

| Tag trong legacy | Số case |
| --- | --- |
| additional_sanction | 1 |
| amended_rule | 3 |
| boundary | 4 |
| condition | 14 |
| cross_document | 6 |
| default_cutoff | 2 |
| definition | 8 |
| direct | 8 |
| equipment | 1 |
| exception | 10 |
| explicit_date | 2 |
| license_points | 5 |
| missing_dependency | 2 |
| missing_facts | 5 |
| money | 21 |
| multi_locator | 14 |
| multiple_facets | 7 |
| negative_conclusion | 2 |
| numeric | 11 |
| reasoning | 7 |
| rule | 1 |
| source_cue_removed | 6 |
| temporal_continuity | 1 |

## Khoảng trống và hành động

| Khoảng trống/rủi ro | Bài development | Còn cần làm |
| --- | --- | --- |
| Tiền/điểm, tiền/chế tài bị thiếu evidence | dev_001–004 controls | Review pool rồi triển khai replay runner |
| Citation tồn tại nhưng không support; đổi hành vi | dev_005–006 | Rubric claim-to-source, không chỉ kiểm locator |
| Mất evidence trước; rewrite đổi chủ thể/biên | dev_007–008 | Runner lưu từng stage, chấm intent preservation |
| Legacy không có multi-turn | dev_009–010 | Review history/current query/full context |
| Thiếu facts/dependency/negative provenance | dev_011–013 | Đo unsafe publication riêng, giữ safety gates |
| Từ chối khi đủ nguồn; date proof/amendment | dev_014–016 | Review derivative, không tự mở proof/gate |
| Chưa có suite sát biên số và temporal blocks | pending_suites | Author gold từng nhánh, review riêng |
| Chưa có unseen held-out | 6 cell, 12 family mục tiêu | Chỉ định custodian/author/reviewer, author ngoài tuning workspace |

## Suite chưa author

- numeric_boundaries: Author riêng các trường hợp vượt tốc độ 9, 10, 20, 21 km/h, không gây tai nạn; review support và mức tiền từng nhánh trước approval. Giữ family exposed, không copy gold 10–20 sang 9/21.
- temporal_blocks: Mỗi một trong 10 blocked chunks cần probe context-only; nhóm mixed/future cần ngày trước/đúng/sau mốc ghi trong nguồn. Chỉ kiểm tra fail-closed của snapshot, không công bố luật tương lai hoặc suy no-penalty. Repealed placeholder không là active support.

## Blueprint held-out (không có query/gold)

| Cell | Target families | Mục tiêu |
| --- | --- | --- |
| direct_new_rule | 2 | Quy tắc/định nghĩa trực tiếp ở article chưa lộ; đủ nguồn để đo unnecessary abstention. |
| new_penalty | 2 | Chủ thể/hành vi mới, yêu cầu nhiều facet nếu nguồn có; đúng clause head và đơn vị. |
| new_cross_document | 2 | Kết hợp rule và áp dụng/chế tài, ngoài rule families đã lộ; không phụ thuộc nguồn ngoài scope. |
| new_missing_facts | 2 | Thiếu một dữ kiện quyết định ở family mới; trả conditional thay vì đoán. |
| new_scope_limit | 2 | Giới hạn thời gian/dependency ở family mới; không paraphrase câu 10/23/29/43. |
| new_multi_turn | 2 | History liên quan/nhiễu ở family chưa dùng tuning; toàn conversation cùng split. |

Số dự kiến là budget tối thiểu thử protocol, không là bằng chứng representative.
Exclusion inventory machine-readable ở coverage.json; còn cần independent semantic exposure audit.
Không có custodian hoặc sealed content ở thời điểm này. C0–C4 vẫn bị chặn.

