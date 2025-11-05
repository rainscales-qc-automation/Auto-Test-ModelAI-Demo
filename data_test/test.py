

def calculate_iou(box1, box2):

    x1_min = box1[0]
    y1_min = box1[1]
    x1_max = box1[0] + box1[2]
    y1_max = box1[1] + box1[3]

    x2_min = box2[0]
    y2_min = box2[1]
    x2_max = box2[0] + box2[2]
    y2_max = box2[1] + box2[3]

    # Calculate intersection
    x_inter_min = max(x1_min, x2_min)
    y_inter_min = max(y1_min, y2_min)
    x_inter_max = min(x1_max, x2_max)
    y_inter_max = min(y1_max, y2_max)

    if x_inter_max < x_inter_min or y_inter_max < y_inter_min:
        return 0.0

    inter_area = (x_inter_max - x_inter_min) * (y_inter_max - y_inter_min)

    # Calculate union
    box1_area = box1[2] * box1[3]
    box2_area = box2[2] * box2[3]
    union_area = box1_area + box2_area - inter_area

    if union_area == 0:
        return 0.0

    return inter_area / union_area


def to_bbox_xywh(coords):
    """
    Chuyển mảng [x1, y1, x2, y2] sang [x, y, w, h]
    x, y: góc trên bên trái
    w, h: chiều rộng và chiều cao
    """
    if len(coords) != 4:
        raise ValueError("Mảng phải gồm đúng 4 phần tử: [x1, y1, x2, y2]")

    x_min, y_min, x_max, y_max = coords
    width = x_max - x_min
    height = y_max - y_min
    return [x_min, y_min, width, height]

# def test_cacul(time_start, time_end, frame):



if __name__ == "__main__":
    print(to_bbox_xywh([156,503,175,283]))
    print(calculate_iou(to_bbox_xywh([964,589,1309,1015]), [1292, 828, 168, 252]))