"""
处理Static_2026_03/GEOSPATIAL文件夹中包含TYP_CD_DES字段的SHP图层
按"-"符号拆分该字段，创建新属性字段存储拆分后的内容
使用pyshp库（无需GDAL）
"""

import os
import shapefile

def get_shp_files(base_dir):
    """获取所有SHP文件路径"""
    shp_files = []
    for root, dirs, files in os.walk(base_dir):
        for file in files:
            if file.endswith('.shp'):
                shp_files.append(os.path.join(root, file))
    return shp_files

def check_typ_cd_des_field(shp_path):
    """检查SHP文件是否包含TYP_CD_DES字段"""
    try:
        sf = shapefile.Reader(shp_path)
        field_names = [field[0] for field in sf.fields[1:]]  # 跳过第一个'DeletionFlag'字段
        sf.close()
        return 'TYP_CD_DES' in field_names
    except Exception as e:
        print(f"检查文件 {shp_path} 时出错: {e}")
        return False

def process_shp_file(shp_path):
    """处理单个SHP文件，拆分TYP_CD_DES字段"""
    print(f"\n{'='*80}")
    print(f"处理文件: {os.path.basename(shp_path)}")
    print(f"路径: {shp_path}")
    
    try:
        # 读取shapefile
        sf = shapefile.Reader(shp_path)
        
        # 获取字段信息
        field_names = [field[0] for field in sf.fields[1:]]
        
        # 检查TYP_CD_DES字段是否存在
        if 'TYP_CD_DES' not in field_names:
            print(f"  ⚠ 未找到TYP_CD_DES字段，跳过")
            sf.close()
            return False
        
        print(f"  ✓ 找到TYP_CD_DES字段")
        
        # 获取所有记录
        records = sf.records()
        feature_count = len(records)
        print(f"  要素总数: {feature_count}")
        
        if feature_count == 0:
            print(f"  ⚠ 文件为空，跳过")
            sf.close()
            return False
        
        # 采样分析TYP_CD_DES字段，确定最大拆分数量
        max_parts = 0
        sample_count = min(100, feature_count)
        
        for i in range(sample_count):
            record = records[i]
            typ_cd_des = record[field_names.index('TYP_CD_DES')]
            if typ_cd_des and isinstance(typ_cd_des, str):
                parts = typ_cd_des.split('-')
                if len(parts) > max_parts:
                    max_parts = len(parts)
        
        print(f"  采样分析: 检查了 {sample_count} 个要素")
        print(f"  最大拆分部分数: {max_parts}")
        
        if max_parts <= 1:
            print(f"  ⚠ TYP_CD_DES字段无需拆分（最多只有1部分），跳过")
            sf.close()
            return False
        
        # 创建新的shapefile写入器
        shp_dir = os.path.dirname(shp_path)
        shp_name = os.path.splitext(os.path.basename(shp_path))[0]
        temp_path = os.path.join(shp_dir, f"{shp_name}_temp.shp")
        
        w = shapefile.Writer(temp_path)
        
        # 复制原有字段
        for field in sf.fields[1:]:  # 跳过'DeletionFlag'
            w.field(*field)
        
        # 添加新字段 TYP_CD_DES_1, TYP_CD_DES_2, ...
        new_field_names = []
        for i in range(1, max_parts + 1):
            field_name = f'TYP_CD_DES_{i}'
            if field_name not in field_names:
                w.field(field_name, 'C', 255)  # C=字符型，255宽度
                new_field_names.append(field_name)
                print(f"  ✓ 创建字段: {field_name}")
            else:
                new_field_names.append(field_name)
                print(f"  ℹ 字段已存在: {field_name}")
        
        # 复制几何类型
        shape_type = sf.shapeType
        
        # 处理每个要素
        print(f"  开始更新要素...")
        updated_count = 0
        error_count = 0
        
        for i in range(feature_count):
            try:
                # 获取几何形状
                shape = sf.shape(i)
                
                # 获取记录
                record = records[i]
                record_list = list(record)
                
                # 获取TYP_CD_DES值并拆分
                typ_cd_des_idx = field_names.index('TYP_CD_DES')
                typ_cd_des = record_list[typ_cd_des_idx]
                
                if typ_cd_des and isinstance(typ_cd_des, str):
                    parts = typ_cd_des.split('-')
                    
                    # 为新字段赋值
                    for j in range(max_parts):
                        if j < len(parts):
                            value = parts[j].strip()  # 去除首尾空格
                        else:
                            value = ''  # 不足的部分填空字符串
                        
                        record_list.append(value)
                else:
                    # 如果TYP_CD_DES为空，所有新字段都填空
                    for j in range(max_parts):
                        record_list.append('')
                
                # 添加记录和几何形状
                w.record(*record_list)
                w.shape(shape)  # 使用shape()方法而不是_shapes.append()
                
                updated_count += 1
                
            except Exception as e:
                error_count += 1
                print(f"  ✗ 处理要素 {i} 时出错: {e}")
        
        # 关闭读写器
        sf.close()
        w.close()
        
        print(f"  ✓ 成功处理 {updated_count} 个要素")
        if error_count > 0:
            print(f"  ⚠ {error_count} 个要素处理失败")
        
        # 备份原文件
        backup_path = os.path.join(shp_dir, f"{shp_name}_backup.shp")
        backup_files = [
            (shp_path, backup_path),
            (shp_path.replace('.shp', '.shx'), backup_path.replace('.shp', '.shx')),
            (shp_path.replace('.shp', '.dbf'), backup_path.replace('.shp', '.dbf')),
            (shp_path.replace('.shp', '.prj'), backup_path.replace('.shp', '.prj')),
        ]
        
        print(f"  正在备份原文件...")
        for src, dst in backup_files:
            if os.path.exists(src):
                if os.path.exists(dst):
                    os.remove(dst)
                os.rename(src, dst)
        
        # 将临时文件重命名为原文件名
        print(f"  正在替换原文件...")
        temp_files = [
            (temp_path, shp_path),
            (temp_path.replace('.shp', '.shx'), shp_path.replace('.shp', '.shx')),
            (temp_path.replace('.shp', '.dbf'), shp_path.replace('.shp', '.dbf')),
            (temp_path.replace('.shp', '.prj'), shp_path.replace('.shp', '.prj')),
        ]
        
        for src, dst in temp_files:
            if os.path.exists(src):
                if os.path.exists(dst):
                    os.remove(dst)
                os.rename(src, dst)
        
        print(f"  ✓ 文件处理完成")
        return True
        
    except Exception as e:
        print(f"  ✗ 处理文件时出错: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """主函数"""
    base_dir = r"D:\Luan\2026-05\2_Singapore\Static_ 2026_03\GEOSPATIAL"
    
    print("="*80)
    print("SHP文件 TYP_CD_DES 字段拆分工具")
    print("="*80)
    print(f"搜索目录: {base_dir}")
    
    # 获取所有SHP文件
    shp_files = get_shp_files(base_dir)
    print(f"\n找到 {len(shp_files)} 个SHP文件")
    
    # 检查哪些文件包含TYP_CD_DES字段
    print("\n正在检查包含TYP_CD_DES字段的文件...")
    target_files = []
    
    for shp_file in shp_files:
        if check_typ_cd_des_field(shp_file):
            target_files.append(shp_file)
            print(f"  ✓ {os.path.basename(os.path.dirname(os.path.dirname(shp_file)))}/"
                  f"{os.path.basename(shp_file)}")
    
    print(f"\n共找到 {len(target_files)} 个包含TYP_CD_DES字段的SHP文件")
    
    if not target_files:
        print("\n没有找到需要处理的文件！")
        return
    
    # 确认是否继续
    print("\n" + "="*80)
    response = input("是否继续处理？(y/n): ")
    if response.lower() != 'y':
        print("操作已取消")
        return
    
    # 处理每个文件
    success_count = 0
    fail_count = 0
    
    for shp_file in target_files:
        if process_shp_file(shp_file):
            success_count += 1
        else:
            fail_count += 1
    
    # 输出总结
    print("\n" + "="*80)
    print("处理完成！")
    print("="*80)
    print(f"成功: {success_count} 个文件")
    print(f"失败: {fail_count} 个文件")
    print(f"总计: {len(target_files)} 个文件")
    
    if success_count > 0:
        print("\n✓ 所有文件的TYP_CD_DES字段已按'-'符号拆分")
        print("  新字段命名规则: TYP_CD_DES_1, TYP_CD_DES_2, ...")

if __name__ == "__main__":
    main()
