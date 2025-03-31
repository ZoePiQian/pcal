import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from calendar import monthrange
from typing import List, Dict
import holidays
import streamlit as st

# 设置 Streamlit 页面配置
st.set_page_config(
    page_title="Seasonality 节假日因素模拟工具",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 初始化 Session State 变量
if 'closed_periods' not in st.session_state:
    st.session_state.closed_periods = []  # 初始化关闭周期列表
if 'prev_end_month' not in st.session_state:
    st.session_state.prev_end_month = None  # 初始化上次选择的结束月份
if 'selected_countries_prev' not in st.session_state:
    st.session_state.selected_countries_prev = []  # 初始化上次选择的国家
if 'adding_closed_period' not in st.session_state:
    st.session_state.adding_closed_period = False  # 初始化添加状态
if 'show_math_question' not in st.session_state:
    st.session_state.show_math_question = False
if 'math_question_answered' not in st.session_state:
    st.session_state.math_question_answered = False
if 'math_correct' not in st.session_state:
    st.session_state.math_correct = False

def start_easter_egg():
    st.session_state.show_math_question = True
    st.session_state.math_question_answered = False
    st.session_state.math_correct = False

# 自定义 CSS 以美化界面，并增加模块之间的间隙
st.markdown("""
    <style>
    .main {
        background-color: #f0f2f6;
    }
    .block-container {
        padding-top: 3rem;
        padding-bottom: 3rem;
    }
    </style>
    """, unsafe_allow_html=True)

# 显示应用的标题
st.title("📅 Seasonality 节假日因素模拟计算")

st.markdown("""
    该工具允许您定义计算月份范围和多个关闭周期，并根据当前日期计算并分配百分比。
    
    - **消费活跃日**：当前日期及之后且不在关闭周期内的日子。
    - **消费关闭日**：指定的关闭周期内的日子，其百分比将累积到前一个消费活跃日。
    - **选择包含节假日的国家**：您可以在**右边侧栏**里选择希望被考虑到节假日的国家，比如您从事跨国市场的计算，您可以一次性加载所需国家的节假日，系统会自动添加这些国家的节假日为【消费关闭周期】。
    """)

# 获取当前日期
current_date = datetime.now().date()
st.info(f"**当前日期**: {current_date}", icon="ℹ️")

# 增加垂直空白
st.markdown("<br>", unsafe_allow_html=True)

# 设置 Seasonality 的时间范围标题
st.header("📆 设置 Seasonality 计算范围")

st.markdown("""
**注意**：模型选择的时间范围越长，考虑经济/环境/人口因子越多，计算时间会越长。
""")

# 固定起始月份为当前月份的第一天
start_of_current_month = current_date.replace(day=1)

# 辅助函数：在给定日期基础上增加指定的月份数
def add_months(source_date, months):
    month = source_date.month - 1 + months
    year = source_date.year + month // 12
    month = month % 12 + 1
    day = min(source_date.day, monthrange(year, month)[1])  # 确保日期不超过目标月份的天数
    return source_date.replace(year=year, month=month, day=day)

# 辅助函数：生成未来指定数量月份的选项列表，格式为 'YYYY-MM'
def generate_month_options(start_date, num_months=12):
    options = []
    for i in range(num_months):
        month_date = add_months(start_date, i)
        options.append(month_date.strftime('%Y-%m'))
    return options

# 生成未来12个月的月份选项
month_options = generate_month_options(start_of_current_month, 12)

# 默认结束月份为当前月份后的两个月
default_end_month = add_months(start_of_current_month, 2).strftime('%Y-%m')

# 用户选择结束月份的下拉菜单
end_month_selected = st.selectbox(
    "选择结束月份",
    options=month_options,
    index=2,  # 默认选择当前月+2
    key="end_month_selector"
)

# 解析所选结束月份，并计算该月的最后一天
end_year, end_month = map(int, end_month_selected.split('-'))
end_day = monthrange(end_year, end_month)[1]  # 获取目标月份的天数
end_of_end_month = datetime(end_year, end_month, end_day).date()

# 显示用户选择的起始和结束月份
col1, col2 = st.columns(2)
with col1:
    st.markdown(f"**起始月份**: {start_of_current_month.strftime('%Y-%m')}")
with col2:
    st.markdown(f"**结束日期**: {end_of_end_month}")

# 增加垂直空白
st.markdown("<br>", unsafe_allow_html=True)

# 辅助函数：获取指定国家列表的节假日列表（包括名称和国家）
def get_all_holidays(start_date: datetime.date, end_date: datetime.date, selected_countries: List[str]) -> List[Dict]:
    country_classes = {
        '中国': holidays.China,
        '美国': holidays.US,
        '英国': holidays.UnitedKingdom,
        '法国': holidays.France,
        '德国': holidays.Germany,
        '意大利': holidays.Italy,
        '西班牙': holidays.Spain,
        '加拿大': holidays.Canada,
        '日本': holidays.Japan
    }
    all_holidays = []
    for country, holiday_class in country_classes.items():
        if country in selected_countries:
            try:
                country_holidays = holiday_class(years=range(start_date.year, end_date.year + 1))
                for date, name in sorted(country_holidays.items()):
                    if start_date <= date <= end_date:
                        all_holidays.append({
                            'date': date,
                            'name': name,
                            'country': country
                        })
            except NotImplementedError:
                st.warning(f"未支持 {country} 的节假日获取。")
    return all_holidays

# 辅助函数：将连续的日期合并为闭合周期
def group_consecutive_dates(dates_with_info: List[Dict]) -> List[dict]:
    if not dates_with_info:
        return []
    # 按日期排序
    sorted_dates = sorted(dates_with_info, key=lambda x: x['date'])
    grouped = []
    start = sorted_dates[0]['date']
    end = sorted_dates[0]['date']
    holidays_in_period = [f"{sorted_dates[0]['name']} ({sorted_dates[0]['country']})"]
    
    for current in sorted_dates[1:]:
        current_date = current['date']
        if current_date == end + timedelta(days=1):
            end = current_date
            holidays_in_period.append(f"{current['name']} ({current['country']})")
        else:
            grouped.append({"start": start, "end": end, "holidays": list(sorted(set(holidays_in_period)))})
            start = current_date
            end = current_date
            holidays_in_period = [f"{current['name']} ({current['country']})"]
    # 添加最后一个周期
    grouped.append({"start": start, "end": end, "holidays": list(sorted(set(holidays_in_period)))})
    return grouped

# 增加垂直空白
st.markdown("<br>", unsafe_allow_html=True)

# 设置关闭周期的标题
st.header("🛑 Planning Calendar 设置")

st.markdown("""
Planning Calendar 关闭周期默认包含所选月份范围内的所选国家法定节假日。您可以添加或删除额外的关闭周期。
""")

# 侧边栏：选择包含节假日的国家
st.sidebar.header("🌍 选择包含节假日的国家")
available_countries = ['中国', '美国', '英国', '法国', '德国', '意大利', '西班牙', '加拿大', '日本']
selected_countries = st.sidebar.multiselect(
    "您可以在这里选择多个国家，设置完成后，模型会自动计算",
    options=available_countries,
    default=['美国','日本','意大利'],  
    help="选择希望考虑其节假日的国家。"
)

# 定义函数：根据索引删除指定的关闭周期
def remove_closed_period(index):
    del st.session_state.closed_periods[index]

# 当结束月份或选中的国家变化时，重置关闭周期为节假日
if (st.session_state.prev_end_month != end_month_selected or
    st.session_state.selected_countries_prev != selected_countries):
    # 获取所有国家的节假日列表（包括名称和国家）
    all_holidays_with_info = get_all_holidays(current_date, end_of_end_month, selected_countries)
    # 将节假日日期和信息传递给分组函数
    holiday_periods = group_consecutive_dates(all_holidays_with_info)
    # 更新关闭周期为所有节假日周期
    st.session_state.closed_periods = holiday_periods
    st.session_state.prev_end_month = end_month_selected  # 更新上次选择的结束月份
    st.session_state.selected_countries_prev = selected_countries  # 记录当前选择的国家
    st.session_state.adding_closed_period = False  # 重置添加状态

# **新增功能**：添加关闭周期时通过日历选择日期
if st.session_state.adding_closed_period:
    st.subheader("📅 选择关闭周期的开始和结束日期")
    cols = st.columns(3)
    with cols[0]:
        new_start_date = st.date_input(
            "开始日期", 
            value=current_date,  # 默认值为今天
            min_value=current_date,  # 设置最小值为今天
            max_value=end_of_end_month, 
            key="new_start_date"
        )
    with cols[1]:
        new_end_date = st.date_input(
            "结束日期", 
            value=end_of_end_month,  # 默认值为 Seasonality 结束日期
            min_value=new_start_date,  # 结束日期不能早于开始日期
            max_value=end_of_end_month, 
            key="new_end_date"
        )
    with cols[2]:
        confirm = st.button("确认添加", key="confirm_add")
        cancel = st.button("取消", key="cancel_add")
    
    if confirm:
        # 确保结束日期不早于开始日期
        if new_end_date < new_start_date:
            st.error("结束日期不能早于开始日期。")
        else:
            # 提取所有国家在新周期内的节假日
            added_holidays = get_all_holidays(new_start_date, new_end_date, selected_countries)
            # 格式化节假日信息
            holiday_names = [f"{holiday['name']} ({holiday['country']})" for holiday in added_holidays]
            st.session_state.closed_periods.append({
                "start": new_start_date,
                "end": new_end_date,
                "holidays": list(sorted(set(holiday_names)))  # 可能为空
            })
            st.session_state.adding_closed_period = False  # 关闭添加状态

    if cancel:
        st.session_state.adding_closed_period = False  # 关闭添加状态

else:
    # 添加关闭周期的按钮
    st.button("➕ 添加关闭周期", on_click=lambda: setattr(st.session_state, 'adding_closed_period', True), key="add_closed_period_button")

# 展示和管理每个关闭周期
for i, period in enumerate(st.session_state.closed_periods):
    with st.expander(f"🛑 关闭周期 {i + 1}"):
        period_cols = st.columns(4)  # 创建四个列用于布局（开始日期，结束日期，节假日，删除按钮）
        with period_cols[0]:
            start_date = st.date_input(
                f"开始日期 {i + 1}",
                value=period['start'],
                min_value=current_date,  # 设置最小值为今天
                max_value=end_of_end_month,
                key=f"start_{i}"
            )
        with period_cols[1]:
            end_date = st.date_input(
                f"结束日期 {i + 1}",
                value=period['end'],
                min_value=start_date,  # 结束日期不能早于开始日期
                max_value=end_of_end_month,
                key=f"end_{i}"
            )
        with period_cols[2]:
            if period['holidays']:
                st.markdown("**节假日**")
                st.markdown(", ".join(period['holidays']))
            else:
                st.markdown("**节假日**: 无")
        with period_cols[3]:
            if st.button("🗑️ 删除", key=f"delete_{i}"):
                remove_closed_period(i)  # 删除指定的关闭周期

        # 更新 Session State 中的关闭周期
        st.session_state.closed_periods[i]['start'] = start_date
        st.session_state.closed_periods[i]['end'] = end_date

        # 重新获取该周期内的所有节假日
        updated_holidays_with_info = get_all_holidays(start_date, end_date, selected_countries)
        updated_holidays = [f"{holiday['name']} ({holiday['country']})" for holiday in updated_holidays_with_info]
        st.session_state.closed_periods[i]['holidays'] = list(sorted(set(updated_holidays)))  # 更新节假日信息

# 显示当前所有关闭周期
st.markdown("### **当前关闭周期:**")
if st.session_state.closed_periods:
    # 使用表格展示并隐藏编号
    closed_periods_data = []
    for i, period in enumerate(st.session_state.closed_periods, 1):
        start_str = period['start'].strftime('%Y-%m-%d')
        end_str = period['end'].strftime('%Y-%m-%d')
        holidays_info = ', '.join(period['holidays']) if period['holidays'] else '无'
        closed_periods_data.append({
            '开始日期': start_str,
            '结束日期': end_str,
            '节假日': holidays_info
        })
    closed_periods_df = pd.DataFrame(closed_periods_data)
    st.dataframe(closed_periods_df.style.set_properties(**{
        'background-color': '#f0f2f6',
        'color': 'black',
        'border-color': '#ffffff'
    }), use_container_width=True)
else:
    st.markdown("**当前关闭周期:** 无")

# 增加垂直空白
st.markdown("<br><br>", unsafe_allow_html=True)

# 百分比分配结果的标题
st.header("📊 Seasonality Fair-share 模型计算结果")
st.markdown("""
    - 请将这个模块的代码自行替换成您的计算需求和算法。以下 fair-share模型只是一个最简单的计算展示
    - 严谨的 Seasonality 模型应该考虑到多种因子，建议基于各地市场的政治/经济/环境/人口因素，给每个因子赋值
    """)

# 检查输入有效性：结束日期是否在起始日期之后
if end_of_end_month >= start_of_current_month:
    # 创建从起始月份第一天到结束月份最后一天的所有日期范围
    all_dates = pd.date_range(start=start_of_current_month, end=end_of_end_month, freq='D')
    df = pd.DataFrame({'date': all_dates})  # 创建一个包含所有日期的数据框

    # Step 1: 添加 'seasonality_type' 列，默认值为 'Fair share'
    df['seasonality_type'] = 'Fair share'

    # Step 2: 标记是否为关闭日
    def is_closed(date, closed_periods: List[dict]) -> bool:
        for period in closed_periods:
            if period['start'] <= date <= period['end']:
                return True
        return False

    df['IsClosed'] = df['date'].apply(lambda d: is_closed(d.date(), st.session_state.closed_periods))

    # Step 3: 标记是否为活跃日（即当前日期及之后）
    df['IsTodayOrAfter'] = df['date'].dt.date >= current_date

    # Step 4: 过滤出剩余的日期，包含今天
    remaining = df[df['IsTodayOrAfter']].copy()

    # Step 5: 提取月份信息
    remaining['month'] = remaining['date'].dt.to_period('M')

    # 初始化一个空的 DataFrame 来存储最终的百分比分配
    final_df = pd.DataFrame()

    # 逐月处理
    for month, group in remaining.groupby('month'):
        # Step 6: 计算活跃日（未关闭）的天数 N 和关闭日的天数 C
        N = (~group['IsClosed']).sum()
        C = group['IsClosed'].sum()
        N_plus_C = N + C if (N + C) > 0 else 1  # 防止除以零

        # Step 7: 分配基础百分比（对活跃日分配 1 / N_plus_C，关闭日分配 0）
        group['BasePercentage'] = group['IsClosed'].apply(lambda x: 0 if x else 1 / N_plus_C)

        # Step 8: 添加索引列以保持日期顺序
        group = group.reset_index(drop=True).reset_index().rename(columns={'index': 'Index'})

        # Step 9: 定义函数：找到当前行前面的最后一个活跃日的索引
        def find_preceding_active_index(current_idx, df_group):
            preceding = df_group[(df_group['Index'] < current_idx) & (~df_group['IsClosed'])]
            if not preceding.empty:
                return preceding.iloc[-1]['Index']
            return None

        # Step 10: 对于每个关闭日，找到其前一个活跃日的索引
        group['PrecedingActiveIndex'] = group.apply(
            lambda row: find_preceding_active_index(row['Index'], group) if row['IsClosed'] else None,
            axis=1
        )

        # Step 11: 筛选出有有效前一个活跃日的关闭日
        closed_days_with_preceding = group[(group['IsClosed']) & (group['PrecedingActiveIndex'].notnull())].copy()

        # Step 12: 按 'PrecedingActiveIndex' 分组，统计每个活跃日前有多少关闭日
        closed_days_grouped = closed_days_with_preceding.groupby('PrecedingActiveIndex').size().reset_index(name='ClosedDaysCount')

        # Step 13: 计算每个活跃日应增加的额外百分比（关闭天数 * (1 / N_plus_C)）
        closed_days_grouped['ExtraPercentage'] = closed_days_grouped['ClosedDaysCount'] * (1 / N_plus_C)

        # Step 14: 将 'ExtraPercentage' 合并回活跃日表格
        group = group.merge(
            closed_days_grouped[['PrecedingActiveIndex', 'ExtraPercentage']],
            left_on='Index',
            right_on='PrecedingActiveIndex',
            how='left'
        )

        # Step 15: 将缺失的 'ExtraPercentage' 值替换为0
        group['ExtraPercentage'] = group['ExtraPercentage'].fillna(0)

        # Step 16: 计算最终的百分比（基础百分比 + ExtraPercentage）
        group['FinalPercentage'] = group['BasePercentage'] + group['ExtraPercentage']

        # Step 17: 对于关闭日，确保 'percentage' 为0；对于活跃日，使用 'FinalPercentage'
        group['percentage'] = group.apply(lambda row: 0 if row['IsClosed'] else row['FinalPercentage'], axis=1)

        # Step 18: 保留所需的列
        month_final = group[['seasonality_type', 'date', 'percentage']].copy()
        month_final['date'] = month_final['date'].dt.strftime('%Y-%m-%d')  # 格式化日期为字符串

        # Step 19: 确保每个月的百分比总和为1（防止浮点误差）
        total_percentage = month_final['percentage'].sum()
        if not np.isclose(total_percentage, 1.0):
            adjustment = 1.0 - total_percentage
            # 查找第一个活跃日
            active_days = month_final[month_final['percentage'] > 0]
            if not active_days.empty:
                first_active_idx = active_days.index[0]
                month_final.at[first_active_idx, 'percentage'] += adjustment

        # 合并到最终的 DataFrame
        final_df = pd.concat([final_df, month_final], ignore_index=True)

    # 创建一个用于显示的副本，避免修改原始数据
    display_df = final_df.copy()

    # 使用 Styler 进行条件格式化，保持 'percentage' 为数值类型
    def highlight_percentage(val):
        try:
            if float(val) > 0:
                return 'background-color: #d3f9d8'  # 绿色背景表示活跃日
            else:
                return 'background-color: #f8d7da'  # 红色背景表示关闭日
        except:
            return ''

    display_df['percentage_display'] = display_df['percentage']

    styled_df = display_df.style.map(
        highlight_percentage,
        subset=['percentage_display']
    ).format(
        {'percentage_display': "{:.2%}"}
    ).set_table_styles([
        {'selector': 'th', 'props': [('background-color', '#4CAF50'), ('color', 'white')]},
        {'selector': 'tr:nth-of-type(even)', 'props': [('background-color', '#f2f2f2')]}
    ])

    # 增加垂直空白
    st.markdown("<br><br>", unsafe_allow_html=True)

    # 显示结果表格
    st.subheader("📈 比例分配结果表")
    st.dataframe(styled_df, use_container_width=True)

    # 创建 CSV 下载内容
    csv = final_df.to_csv(index=False).encode('utf-8')
    st.download_button(
        label="⬇️ 下载结果为 CSV",
        data=csv,
        file_name='seasonality_distribution.csv',
        mime='text/csv',
    )

    # 增加垂直空白
    st.markdown("<br><br>", unsafe_allow_html=True)

    # 代码展示模块的标题
    st.header("💻 应用源代码展示")

    # 读取当前文件的代码
    try:
        with open(__file__, 'r', encoding='utf-8') as f:
            app_code = f.read()
    except Exception as e:
        app_code = f"无法读取源代码: {e}"

    # 显示代码，使用代码块
    st.code(app_code, language='python')

else:
    # 当输入无效时，显示提示信息
    st.info("请设置结束月份。关闭周期为可选项，您可以根据需要添加。")

# 增加垂直空白
st.markdown("<br><br>", unsafe_allow_html=True)

# 侧边栏关于应用的信息
st.sidebar.markdown("""
---
**👩‍💻 开发者**: 小狗波粒  

**📧 联系方式**: 

""")

# 添加微信二维码彩蛋
if st.sidebar.button("📲 联系方式: 小狗微信", key="weixin_button"):
    start_easter_egg()

# 如果彩蛋触发，显示数学问题在侧边栏
if st.session_state.show_math_question:
    st.sidebar.markdown("### 🎉 你发现了彩蛋！")
    st.sidebar.markdown("#### 回答以下数学问题以获取微信二维码。")
    
    # 设计一个简单的数学问题
    math_question = "小狗波粒藏了一些苹果在狗窝里，有天晚上波粒偷偷吃掉3个后，发现还剩下7个苹果。请问波粒最初有多少个苹果藏在了狗窝？"
    st.sidebar.write(math_question)
    
    user_answer = st.sidebar.number_input("请输入你的答案", min_value=0, step=1, key="math_answer")
    
    # 使用列布局来分布按钮
    col_submit, col_close = st.sidebar.columns([1,1])
    
    with col_submit:
        if st.sidebar.button("提交答案", key="submit_math_answer"):
            correct_answer = 10  # 7 + 3
            if user_answer == correct_answer:
                st.sidebar.success("恭喜你，回答正确！这是小狗的微信二维码：")
                # 显示微信二维码图片
                wechat_qr_path = "./images/wechat_qr.png"  # 使用本地路径
                st.sidebar.image(wechat_qr_path, caption="微信二维码", use_container_width=False)
                st.session_state.math_correct = True
                st.session_state.show_math_question = False  # 自动关闭问题
            else:
                st.sidebar.error("回答错误！这是另一张可爱的小狗图片：")
                # 显示错误图片
                dog_error_path = "./images/dog_error.png"  # 使用本地路径
                st.sidebar.image(dog_error_path, caption="再试一次吧~", use_container_width=False)
                st.session_state.math_correct = False
                st.session_state.math_question_answered = True

    with col_close:
        if st.sidebar.button("关闭", key="close_easter_egg"):
            st.session_state.show_math_question = False

# 增加垂直空白
st.markdown("<br><br>", unsafe_allow_html=True)
