"""

State lattice planner with model predictive trajectory generator

author: Atsushi Sakai(Atsushi_twi)

"""
import sys

from matplotlib import pyplot as plt
import numpy as np
import math
import pandas as pd
import model_predictive_trajectory_generator as planner
import motion_model

table_path = "./lookuptables.csv"

show_animation = True


def search_nearest_one_from_lookuptable(tx, ty, tyaw, lookup_table):
    mind = float("inf")
    minid = -1

    for (i, table) in enumerate(lookup_table):

        dx = tx - table[0]
        dy = ty - table[1]
        dyaw = tyaw - table[2]
        d = math.sqrt(dx ** 2 + dy ** 2 + dyaw ** 2)
        if d <= mind:
            minid = i
            mind = d

    return lookup_table[minid]


def get_lookup_table():
    data = pd.read_csv(table_path)

    return np.array(data)


def generate_path(cur_states, target_states, k0):
    # x, y, yaw, s, km, kf
    lookup_table = get_lookup_table()
    result = []

    for state in target_states:
        bestp = search_nearest_one_from_lookuptable(
            state[0], state[1], state[2], lookup_table)
        print("bestp", bestp)

        target = motion_model.State(x=state[0], y=state[1], yaw=state[2])
        init_p = np.matrix(
            [math.sqrt((state[0]) ** 2 + (state[1]) ** 2), bestp[4], bestp[5]]).T
        if init_p[0]>50:
            print("cur states: ", cur_states)
            print("target states: ", state)

        x, y, yaw, p = planner.optimize_trajectory(cur_states, target, k0, init_p)

        if x is not None:
            print("find good path")
            result.append(
                [x[-1], y[-1],yaw[-1], float(p[0]), float(p[1]), float(p[2])])

    print("finish path generation")
    return result


def calc_uniform_polar_states(cur_states,nxy, nh, d, a_min, a_max, p_min, p_max):
    """
    calc uniform state

    :param nxy: number of position sampling
    :param nh: number of heading sampleing
    :param d: distance of terminal state
    :param a_min: position sampling min angle
    :param a_max: position sampling max angle
    :param p_min: heading sampling min angle
    :param p_max: heading sampling max angle
    :return: states list
    """

    angle_samples = [i / (nxy - 1) for i in range(nxy)]
    print("angle_samples", angle_samples)
    states = sample_states(cur_states, angle_samples, a_min, a_max, d, p_max, p_min, nh)


    return states


def calc_biased_polar_states(goal_angle, ns, nxy, nh, d, a_min, a_max, p_min, p_max):
    """
    calc biased state

    :param goal_angle: goal orientation for biased sampling
    :param ns: number of biased sampling
    :param nxy: number of position sampling
    :param nxy: number of position sampling
    :param nh: number of heading sampleing
    :param d: distance of terminal state
    :param a_min: position sampling min angle
    :param a_max: position sampling max angle
    :param p_min: heading sampling min angle
    :param p_max: heading sampling max angle
    :return: states list
    """

    asi = [a_min + (a_max - a_min) * i / (ns - 1) for i in range(ns - 1)]
    cnav = [math.pi - abs(i - goal_angle) for i in asi]

    cnav_sum = sum(cnav)
    cnav_max = max(cnav)

    # normalize
    cnav = [(cnav_max - cnav[i]) / (cnav_max * ns - cnav_sum)
            for i in range(ns - 1)]

    csumnav = np.cumsum(cnav)
    di = []
    li = 0
    for i in range(nxy):
        for ii in range(li, ns - 1):
            if ii / ns >= i / (nxy - 1):
                di.append(csumnav[ii])
                li = ii - 1
                break

    states = sample_states(di, a_min, a_max, d, p_max, p_min, nh)

    return states


def calc_lane_states(l_center, l_heading, l_width, v_width, d, nxy):
    """

    calc lane states

    :param l_center: lane lateral position
    :param l_heading:  lane heading
    :param l_width:  lane width
    :param v_width: vehicle width
    :param d: longitudinal position
    :param nxy: sampling number
    :return: state list
    """
    xc = math.cos(l_heading) * d + math.sin(l_heading) * l_center
    # yc = math.sin(l_heading) * d - math.cos(l_heading) * l_center
    yc = math.sin(l_heading) * d - math.cos(l_heading) * l_center

    states = []
    for i in range(nxy):
        delta = -0.5 * (l_width - v_width) + \
            (l_width - v_width) * i / (nxy - 1)
        # print("delta", delta)
        xf = xc - delta * math.sin(l_heading)
        yf = yc + delta * math.cos(l_heading)
        yawf = l_heading
        states.append([xf, yf, yawf])

    return states


def calc_lane_states_linear(l_center, l_heading, l_width, v_width, d, nxy):
    """

    calc lane states

    :param l_center: lane lateral position
    :param l_heading:  lane heading
    :param l_width:  lane width
    :param v_width: vehicle width
    :param d: longitudinal position
    :param nxy: sampling number
    :return: state list
    """
    xc = math.cos(l_heading) * d*1.1
    yc = math.sin(l_heading) * d*1.1

    yawc = l_heading
    states = []
    states.append([xc, yc, yawc])

    return states




def sample_states(cur_states, angle_samples, a_min, a_max, d, p_max, p_min, nh):
    #curstates = [x,y,yaw, v]
    states = []
    for i in angle_samples:
        a = cur_states[2]+a_min + (a_max - a_min) * i
        if a>2*np.pi:
            a-=2*np.pi
        print("a", a)

        for j in range(nh):
            xf = cur_states[0]+d * math.cos(a)
            yf = cur_states[1]+d * math.sin(a)
            if nh == 1:
                yawf = (p_max - p_min) / 2 + a
            else:
                yawf = p_min + (p_max - p_min) * j / (nh - 1) + a
            states.append([xf, yf, yawf])

    return states


def uniform_terminal_state_sampling_test1(cur_states, ax=None):

    k0 = 0.0
    nxy = 3
    nh = 2
    d = 2
    a_min = - math.radians(45.0)
    a_max = math.radians(45.0)
    p_min = - math.radians(40.0)
    p_max = math.radians(40.0)
    # a_min = - math.radians(45.0)
    # a_max = math.radians(45.0)
    # p_min = - math.radians(45.0)
    # p_max = math.radians(45.0)
    target_states = calc_uniform_polar_states(cur_states, nxy, nh, d, a_min, a_max, p_min, p_max)
    result = generate_path(cur_states,target_states, k0)

    for table in result:
        print("table", table)
        xc, yc, yawc = motion_model.generate_trajectory(cur_states,
            table[3], table[4], table[5], k0)

        if show_animation:
            if ax==None:
                plt.plot(xc, yc, "-r")
            else:
                ax.plot(xc, yc, "-r")
                

    # if show_animation:
        # plt.grid(True)
        # plt.axis("equal")
        # plt.show()

    # print("Done")


def uniform_terminal_state_sampling_test2():
    k0 = 0.1
    nxy = 6
    nh = 3
    d = 20
    a_min = - math.radians(-10.0)
    a_max = math.radians(45.0)
    p_min = - math.radians(20.0)
    p_max = math.radians(20.0)
    states = calc_uniform_polar_states(nxy, nh, d, a_min, a_max, p_min, p_max)
    result = generate_path(states, k0)

    for table in result:
        xc, yc, yawc = motion_model.generate_trajectory(
            table[3], table[4], table[5], k0)

        if show_animation:
            plt.plot(xc, yc, "-r")

    if show_animation:
        plt.grid(True)
        plt.axis("equal")
        plt.show()

    print("Done")


def biased_terminal_state_sampling_test1():
    k0 = 0.0
    nxy = 30
    nh = 2
    d = 20
    a_min = math.radians(-45.0)
    a_max = math.radians(45.0)
    p_min = - math.radians(20.0)
    p_max = math.radians(20.0)
    ns = 100
    goal_angle = math.radians(0.0)
    states = calc_biased_polar_states(
        goal_angle, ns, nxy, nh, d, a_min, a_max, p_min, p_max)
    result = generate_path(states, k0)

    for table in result:
        xc, yc, yawc = motion_model.generate_trajectory(
            table[3], table[4], table[5], k0)
        if show_animation:
            plt.plot(xc, yc, "-r")

    if show_animation:
        plt.grid(True)
        plt.axis("equal")
        plt.show()


def biased_terminal_state_sampling_test2():
    k0 = 0.0
    nxy = 30
    nh = 1
    d = 20
    a_min = math.radians(0.0)
    a_max = math.radians(45.0)
    p_min = - math.radians(20.0)
    p_max = math.radians(20.0)
    ns = 100
    goal_angle = math.radians(30.0)
    states = calc_biased_polar_states(
        goal_angle, ns, nxy, nh, d, a_min, a_max, p_min, p_max)
    result = generate_path(states, k0)

    for table in result:
        xc, yc, yawc = motion_model.generate_trajectory(
            table[3], table[4], table[5], k0)

        if show_animation:
            plt.plot(xc, yc, "-r")

    if show_animation:
        plt.grid(True)
        plt.axis("equal")
        plt.show()


def lane_state_sampling_test1(cur_states, ax=None):
    k0 = 0.0

    l_center = 1.0
    l_center2 = -1.0
    l_center3 = 1.0
    l_center4 = -1.0
    # cur_states[2]=1.0
    # l_heading = cur_states[2]+math.radians(10.0)
    # l_heading2 = cur_states[2]+math.radians(-10.0)
    # l_heading = math.radians(10.0)
    l_heading = cur_states[2]
    if l_heading<0.0:
        l_heading=abs(l_heading)
    if l_heading>np.pi/4:
        l_heading=np.pi/4

    # print("l_heading", l_heading*180/np.pi)

    l_width = 1.0
    v_width = 0.0
    d = 4.0
    d2 = 3.5
    nxy = 3

    targetstates0 = calc_lane_states_linear(l_center, l_heading, l_width, v_width, d, nxy)
    targetstates = calc_lane_states(l_center, l_heading, l_width, v_width, d, nxy)
    targetstates2 = calc_lane_states( l_center2, l_heading, l_width, v_width, d, nxy)
    
    ''' plot target goals
    for tstates in targetstates0:
        if ax==None:
            plt.scatter(tstates[0], tstates[1], facecolor='black',edgecolor='black')      #final point
        else:
            ax.scatter(tstates[0], tstates[1], facecolor='black',edgecolor='black')      #final point

    for tstates in targetstates:
        if ax==None:
            plt.scatter(tstates[0], tstates[1], facecolor='red',edgecolor='red')      #final point
        else:
            ax.scatter(tstates[0], tstates[1], facecolor='red',edgecolor='red')      #final point

    for tstates in targetstates2:
        if ax==None:
            plt.scatter(tstates[0], tstates[1], facecolor='blue',edgecolor='blue')      #final point
    '''
    
    cur_states_mod=[0,0,np.pi/6,0]
    # cur_states_mod=[0,0,0.0,0]
    result0 = generate_path(cur_states_mod,targetstates0, k0)
    result = generate_path(cur_states_mod,targetstates, k0)
    result2 = generate_path(cur_states_mod,targetstates2, k0)
    # result3 = generate_path(cur_states,targetstates3, k0)
    # result4 = generate_path(cur_states,targetstates4, k0)

    # print("cur_states[0]", cur_states[0])
    trjs=[]

    for table in result0:
        xc, yc, yawc = motion_model.generate_trajectory(cur_states_mod,
            table[3], table[4], table[5], k0)

        for i in range(len(xc)):
            if cur_states[2]>np.pi/2 and cur_states[2]<3*np.pi/2:
                xc[i]=-xc[i]
            xc[i]+=cur_states[0]

        for j in range(len(yc)):
            if cur_states[2]>np.pi:
                yc[j]=-yc[j]
            yc[j]+=cur_states[1]
        trjs.append([xc, yc, yawc])

        if show_animation:
            if ax==None:
                plt.plot(xc, yc, "-r")
            else:
                ax.plot(xc, yc, "-r")


    for table in result:
        xc, yc, yawc = motion_model.generate_trajectory(cur_states_mod,
            table[3], table[4], table[5], k0)
        for i in range(len(xc)):
            if cur_states[2]>np.pi/2 and cur_states[2]<3*np.pi/2:
                xc[i]=-xc[i]
            xc[i]+=cur_states[0]

        for j in range(len(yc)):
            if cur_states[2]>np.pi:
                yc[j]=-yc[j]
            yc[j]+=cur_states[1]
        trjs.append([xc, yc, yawc])

        if show_animation:
            if ax==None:
                plt.plot(xc, yc, "-r")
            else:
                ax.plot(xc, yc, "-r")

    for table in result2:
        xc, yc, yawc = motion_model.generate_trajectory(cur_states_mod,
            table[3], table[4], table[5], k0)
        for i in range(len(xc)):
            if cur_states[2]>np.pi/2 and cur_states[2]<3*np.pi/2:
                xc[i]=-xc[i]
            xc[i]+=cur_states[0]

        for j in range(len(yc)):
            if cur_states[2]>np.pi:
                yc[j]=-yc[j]
                
            yc[j]+=cur_states[1]
        trjs.append([xc, yc, yawc])


        if show_animation:
            if ax==None:
                plt.plot(xc, yc, "-r")
            else:
                ax.plot(xc, yc, "-r")

    # print(trjs)
    return trjs

    '''

    for table in result3:
        xc, yc, yawc = motion_model.generate_trajectory(cur_states,
            table[3], table[4], table[5], k0)
        print("xc, yc", xc,yc)

        if show_animation:
            plt.plot(xc, yc, "-b")
            # if ax==None:
                # plt.plot(xc, yc, "-r")
            # else:
                # ax.plot(xc, yc, "-r")

    for table in result4:
        xc, yc, yawc = motion_model.generate_trajectory(cur_states,
            table[3], table[4], table[5], k0)

        if show_animation:
            plt.plot(xc, yc, "-y")
            # if ax==None:
                # plt.plot(xc, yc, "-r")
            # else:
                # ax.plot(xc, yc, "-r")


    '''
    # if show_animation:
        # plt.grid(True)
        # plt.axis("equal")
        # plt.show()



def main():
    # cur_states=[1,1, np.pi/3,0]
    cur_states=[2.0,0.0, np.pi/4,0]
    # uniform_terminal_state_sampling_test1(cur_states)
    # uniform_terminal_state_sampling_test2()
    # biased_terminal_state_sampling_test1()
    # biased_terminal_state_sampling_test2()
    lane_state_sampling_test1(cur_states)



if __name__ == '__main__':
    main()
